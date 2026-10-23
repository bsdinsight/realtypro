# -*- coding: utf-8 -*-
"""Một lượt nạp — tải tệp lên, chạy thử, rồi ghi.

Chạy thử và chạy thật là MỘT đoạn mã
-------------------------------------
Khác nhau đúng một cờ. Viết hai đoạn riêng thì sớm muộn chúng nói hai
chuyện khác nhau, và lúc đó chạy thử còn tệ hơn không có — vì người dùng
đã tin vào nó.

Cách lấy được chạy thử THẬT: làm mọi thứ bên trong một savepoint, kể cả
ghi và tính lại, rồi nếu là chạy thử thì cuộn lại. Nhờ vậy phần đối
chiếu công thức cũng chạy trên dữ liệu vừa ghi, chứ không so với số cũ
còn nằm đó.

Nhật ký thì phải SỐNG SÓT qua cuộn lại, nên nó được gom vào một danh
sách Python trong lúc chạy và chỉ tạo bản ghi sau khi savepoint đã đóng.
Ghi nhật ký vào bảng ngay trong savepoint là cuộn lại mất luôn lý do —
đúng thứ duy nhất mà một lượt chạy thử sinh ra.

Nhật ký không được nói dối
---------------------------
Một dòng "đã ghi" phải nghĩa là đã ghi. Nên các dòng ghi được giữ ở danh
sách tạm cho tới khi biết chắc cả sheet đi qua được phần kiểm bắt buộc;
sheet bị bỏ thì chúng chuyển thành "bỏ qua" kèm lý do, chứ không nằm lại
dưới nhãn "đã ghi" trong khi không có gì vào cơ sở dữ liệu.
"""
import base64
import logging
from datetime import datetime, timedelta

import pytz

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from . import doc_nguon
from .eam_import_template import DICH

_logger = logging.getLogger(__name__)


class _Cuon(Exception):
    """Cờ nội bộ để cuộn savepoint sau khi chạy thử xong."""


KET_QUA = [
    ('ghi', 'Đã ghi'),
    ('khop', 'Đối chiếu — khớp'),
    ('lech', 'Đối chiếu — LỆCH'),
    ('bo_qua', 'Bỏ qua'),
    ('canh_bao', 'Cảnh báo'),
    ('loi', 'Lỗi'),
]


class EamImportRun(models.Model):
    _name = 'eam.import.run'
    _description = 'Lượt nạp dữ liệu'
    _inherit = ['mail.thread']
    _order = 'create_date desc, id desc'
    _rec_name = 'display_name'

    template_id = fields.Many2one(
        'eam.import.template', string='Mẫu nạp', required=True,
        ondelete='restrict', tracking=True)
    kieu = fields.Selection(related='template_id.kieu')
    plant_id = fields.Many2one(
        'eam.location', string='Nhà máy', required=True,
        domain="[('location_type', '=', 'plant')]", tracking=True)

    file = fields.Binary(string='Tệp', attachment=True, required=True)
    filename = fields.Char(string='Tên tệp')

    state = fields.Selection(
        [('nhap', 'Nháp'),
         ('thu', 'Đã chạy thử'),
         ('xong', 'Đã nạp'),
         ('loi', 'Có lỗi')],
        string='Trạng thái', default='nhap', required=True, tracking=True)

    ghi_de = fields.Boolean(
        string='Cho phép ghi đè ngày đã nạp', tracking=True,
        help='Mặc định là từ chối: nạp lại cùng một ngày phải là chủ ý, '
             'không phải tai nạn. Bật cờ này khi nhà máy gửi lại tờ báo '
             'cáo đã sửa.')

    ngay_dau = fields.Date(string='Từ ngày', readonly=True)
    ngay_cuoi = fields.Date(string='Đến ngày', readonly=True)
    so_ngay = fields.Integer(string='Số ngày đọc được', readonly=True)
    so_ghi = fields.Integer(string='Ô đã ghi', readonly=True)
    so_khop = fields.Integer(string='Đối chiếu khớp', readonly=True)
    so_lech = fields.Integer(string='Đối chiếu LỆCH', readonly=True)
    so_bo_qua = fields.Integer(string='Bỏ qua', readonly=True)
    so_canh_bao = fields.Integer(string='Cảnh báo', readonly=True)
    so_loi = fields.Integer(string='Lỗi', readonly=True)

    log_ids = fields.One2many('eam.import.log', 'run_id', string='Nhật ký')
    tom_tat = fields.Text(string='Kết quả', readonly=True)

    company_id = fields.Many2one(
        'res.company', default=lambda s: s.env.company)

    @api.depends('template_id', 'filename')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '%s — %s' % (
                rec.template_id.name or '', rec.filename or _('chưa có tệp'))

    @api.onchange('template_id')
    def _onchange_template(self):
        if self.template_id.plant_id and not self.plant_id:
            self.plant_id = self.template_id.plant_id

    # ==================================================================
    # Nút
    # ==================================================================
    def action_thu(self):
        for rec in self:
            rec._chay(thu=True)
        return True

    def action_nap(self):
        for rec in self:
            rec._chay(thu=False)
        return True

    def action_lam_lai(self):
        """Về nháp, xoá nhật ký — để sửa mẫu rồi thử lại trên cùng tệp."""
        for rec in self:
            rec.log_ids.unlink()
            rec.write({'state': 'nhap', 'tom_tat': False, 'so_ghi': 0,
                       'so_khop': 0, 'so_lech': 0, 'so_bo_qua': 0,
                       'so_canh_bao': 0, 'so_loi': 0, 'so_ngay': 0,
                       'ngay_dau': False, 'ngay_cuoi': False})
        return True

    # ==================================================================
    # Động cơ
    # ==================================================================
    def _chay(self, thu):
        self.ensure_one()
        if not self.file:
            raise UserError(_('Chưa tải tệp lên.'))
        if not self.template_id.map_ids:
            raise UserError(_(
                'Mẫu "%s" chưa có dòng ánh xạ nào — chạy sẽ không đọc gì.',
                self.template_id.name))
        self.log_ids.unlink()

        nd = base64.b64decode(self.file)
        nk = []          # nhật ký, sống sót qua cuộn lại
        ngay = set()

        try:
            with self.env.cr.savepoint():
                if self.template_id.kieu == 'bieu':
                    self._chay_bieu(nd, nk, ngay)
                else:
                    self._chay_bang(nd, nk, ngay)
                if thu:
                    raise _Cuon()
        except _Cuon:
            self.env.invalidate_all()
        except doc_nguon.LoiNguon as e:
            self.env.invalidate_all()
            nk.append({'ket_qua': 'loi', 'nhan': _('Đọc tệp'),
                       'ly_do': str(e)})
        except Exception as e:                           # noqa: BLE001
            # Một sheet hỏng không được làm mất cả nhật ký: người dùng cần
            # thấy những gì ĐÃ đọc được để biết sửa mẫu ở đâu. Nên lỗi đi
            # vào nhật ký thay vì bật ra thành hộp thoại rồi cuộn mất hết.
            self.env.invalidate_all()
            _logger.exception('eam_import: lượt nạp %s đổ', self.id)
            nk.append({'ket_qua': 'loi', 'nhan': _('Lỗi không lường trước'),
                       'ly_do': '%s: %s' % (type(e).__name__, str(e)[:500])})

        self.env['eam.import.log'].create(
            [dict(d, run_id=self.id) for d in nk])

        dem = dict.fromkeys([k for k, _l in KET_QUA], 0)
        for d in nk:
            k = d.get('ket_qua') or 'bo_qua'
            dem[k] = dem.get(k, 0) + 1
        self.write({
            'state': 'loi' if dem['loi'] else ('thu' if thu else 'xong'),
            'so_ghi': dem['ghi'], 'so_khop': dem['khop'],
            'so_lech': dem['lech'], 'so_bo_qua': dem['bo_qua'],
            'so_canh_bao': dem['canh_bao'], 'so_loi': dem['loi'],
            'so_ngay': len(ngay),
            'ngay_dau': min(ngay) if ngay else False,
            'ngay_cuoi': max(ngay) if ngay else False,
            'tom_tat': self._tom_tat(thu, dem, ngay),
        })
        return True

    def _tom_tat(self, thu, dem, ngay):
        dong = [_('CHẠY THỬ — không ghi gì vào dữ liệu.') if thu
                else _('Đã nạp vào dữ liệu.')]
        if ngay:
            dong.append(_('Ngày đọc được: %(n)d (%(a)s → %(b)s)',
                          n=len(ngay), a=min(ngay), b=max(ngay)))
        dong.append(_('Ô ghi %(g)d · khớp %(k)d · LỆCH %(l)d · bỏ qua '
                      '%(b)d · cảnh báo %(c)d · lỗi %(e)d',
                      g=dem['ghi'], k=dem['khop'], l=dem['lech'],
                      b=dem['bo_qua'], c=dem['canh_bao'], e=dem['loi']))
        if dem['loi']:
            dong.append(_('Có lỗi — xem nhật ký. Dữ liệu của sheet bị lỗi '
                          'KHÔNG được ghi.'))
        if dem['lech']:
            dong.append(_('Có dòng đối chiếu LỆCH: con số nhà máy tự tính '
                          'khác con số hệ tính ra. Số của tệp vẫn được ghi '
                          'nguyên; khoảng lệch nằm trong nhật ký.'))
        return '\n'.join(dong)

    # ------------------------------------------------------------------
    # Tờ biểu
    # ------------------------------------------------------------------
    def _chay_bieu(self, nd, nk, ngay_da_doc):
        mau = self.template_id
        wb = doc_nguon.mo_workbook(nd)
        ten_sheet = [mau.sheet.strip()] if (mau.sheet or '').strip() \
            else list(wb.sheetnames)

        chuoi = self.env['eam.chain'].search(
            [('plant_id', '=', self.plant_id.id)], limit=1)
        co_ghi_bac = False

        for ts in ten_sheet:
            if ts not in wb.sheetnames:
                nk.append({'ket_qua': 'loi', 'sheet': ts,
                           'nhan': _('Sheet'),
                           'ly_do': _('tệp không có sheet tên "%s" — tệp có: '
                                      '%s', ts, ', '.join(wb.sheetnames))})
                continue
            ws = wb[ts]
            tron = doc_nguon.ban_do_tron(ws)

            ngay = self._ngay_cua_sheet(ws, ts, tron, nk)
            if not ngay:
                continue
            if not self._ngay_dung_duoc(ngay, ts, nk):
                continue

            ngay_da_doc.add(ngay)
            if self._nap_mot_sheet(ws, ts, ngay, tron, nk, chuoi):
                co_ghi_bac = True

        if chuoi and co_ghi_bac:
            # ``loss_kwh`` là trường tính CÓ LƯU, và nó tra sản lượng bậc
            # đứng trước bằng search — quan hệ Odoo không theo dõi được.
            # Ghi bậc sau trước bậc trước thì dòng đã ghi giữ số cũ, mà
            # số cũ trông y hệt số mới.
            chuoi.node_ids._tinh_lai_ngay()
            self._kiem_ton_that_am(chuoi, ngay_da_doc, nk)

    def _kiem_ton_that_am(self, chuoi, cac_ngay, nk):
        """Bậc sau cao hơn bậc trước — gần như luôn là lệch đơn vị.

        Điện không tăng lên khi đi qua một máy biến áp. Một dòng mang
        tổn thất âm nghĩa là hai bậc không cùng đơn vị, hoặc hai ô bị
        khai đổi chỗ. Cả hai đều cho ra con số dương trông hợp lý ở mọi
        chỗ khác.
        """
        if not cac_ngay:
            return
        am = self.env['eam.chain.day'].search([
            ('chain_id', '=', chuoi.id),
            ('date', 'in', list(cac_ngay)),
            ('node_type', '=', 'san_luong'),
            ('loss_kwh', '<', 0)])
        for d in am:
            nk.append({
                'ket_qua': 'canh_bao', 'ngay': d.date,
                'nhan': _('Bậc %s', d.node_id.code or d.node_id.name),
                'tri': d.energy, 'tri_ta': d.energy_truoc,
                'lech_pct': d.loss_pct,
                'ly_do': _('tổn thất ÂM %(l).1f kWh: bậc này (%(a).1f) cao '
                           'hơn bậc trước (%(b).1f). Điện không tăng khi đi '
                           'qua một bậc — hãy soi lại hệ số đơn vị hoặc xem '
                           'hai ô có bị khai đổi chỗ.',
                           l=d.loss_kwh, a=d.energy, b=d.energy_truoc)})

    def _ngay_cua_sheet(self, ws, ts, tron, nk):
        """Ngày báo cáo, sau khi đối chiếu ô ngày với tên sheet."""
        mau = self.template_id
        gt, chu = doc_nguon.doc_o(ws, mau.o_ngay, tron)
        ngay = doc_nguon.ra_ngay(gt)
        if not ngay:
            nk.append({
                'ket_qua': 'loi', 'sheet': ts, 'dia_chi': mau.o_ngay,
                'nhan': _('Ngày báo cáo'), 'tri_tho': str(gt)[:120],
                'ly_do': _('ô ngày không đọc được thành ngày%s',
                           ' — ' + chu if chu else '')})
            return None
        if mau.kiem_ten_sheet:
            ngay_ts = doc_nguon.ngay_tu_ten_sheet(ts)
            if ngay_ts and ngay_ts != ngay:
                nk.append({
                    'ket_qua': 'loi', 'sheet': ts, 'ngay': ngay,
                    'dia_chi': mau.o_ngay, 'nhan': _('Ngày báo cáo'),
                    'tri_tho': str(ngay),
                    'ly_do': _('tên sheet nói ngày %(a)s, ô %(o)s nói ngày '
                               '%(b)s. Thường là sheet được nhân bản mà '
                               'quên sửa ô ngày — ghi theo ô thì đè lên dữ '
                               'liệu của ngày cũ. Bỏ qua cả sheet.',
                               a=ngay_ts, o=mau.o_ngay, b=ngay)})
                return None
        return ngay

    def _ngay_dung_duoc(self, ngay, ts, nk):
        hn = fields.Date.context_today(self)
        if ngay > hn:
            nk.append({'ket_qua': 'loi', 'sheet': ts, 'ngay': ngay,
                       'nhan': _('Ngày báo cáo'),
                       'ly_do': _('ngày %(a)s nằm trong tương lai (hôm nay '
                                  '%(b)s). Gần như luôn là lỗi ô ngày hoặc '
                                  'lỗi múi giờ của máy xuất tệp.',
                                  a=ngay, b=hn)})
            return False
        if not self.ghi_de:
            da = self._da_co_du_lieu(ngay)
            if da:
                nk.append({'ket_qua': 'loi', 'sheet': ts, 'ngay': ngay,
                           'nhan': _('Ngày báo cáo'),
                           'ly_do': _('ngày %(a)s đã có dữ liệu (%(b)s). '
                                      'Bật cờ "cho phép ghi đè" nếu đây là '
                                      'bản sửa.', a=ngay, b=', '.join(da))})
                return False
        return True

    def _da_co_du_lieu(self, ngay):
        """Những bảng đã có dữ liệu của nhà máy này trong ngày này."""
        co = []
        dom = [('plant_id', '=', self.plant_id.id), ('date', '=', ngay)]
        if self.env['eam.solar.weather'].search_count(dom):
            co.append(_('khí tượng'))
        if self.env['eam.solar.kpi'].search_count(dom):
            co.append(_('hiệu suất'))
        n = self.env['eam.chain.day'].search_count(dom)
        if n:
            co.append(_('%d bậc đo', n))
        return co

    # ------------------------------------------------------------------
    def _nap_mot_sheet(self, ws, ts, ngay, tron, nk, chuoi):
        """Đọc mọi dòng ánh xạ của một sheet rồi ghi theo thứ tự đích.

        Trả về ``True`` nếu có ghi vào bậc đo — để phần gọi biết có cần
        tính lại tổn thất hay không.
        """
        gom = {'weather': {}, 'kpi': {}, 'node': {}, 'tag': []}
        doi_chieu = []
        thieu_bb = []
        nk_tam = []          # dòng "đã ghi", chỉ nhận khi sheet đi qua được

        for dong in self.template_id.map_ids:
            if ':' in (dong.o or ''):
                self._doc_dai_gio(ws, ts, ngay, tron, dong, nk_tam, gom)
                continue
            gt, chu = doc_nguon.doc_o(ws, dong.o, tron)
            if gt is None or (isinstance(gt, str) and not gt.strip()):
                if dong.bat_buoc:
                    thieu_bb.append(dong.name)
                nk.append({
                    'ket_qua': 'loi' if dong.bat_buoc else 'bo_qua',
                    'sheet': ts, 'ngay': ngay, 'dia_chi': dong.o,
                    'nhan': dong.name, 'dich_text': self._nhan_dich(dong),
                    'ly_do': chu or _('ô rỗng')})
                continue

            tri = self._doi_tri(dong, gt, ts, ngay, nk)
            if tri is None:
                continue
            if dong.chi_doi_chieu:
                doi_chieu.append((dong, tri, gt))
                continue
            self._xep_vao_gom(dong, tri, gom, ngay)
            nk_tam.append({
                'ket_qua': 'ghi', 'sheet': ts, 'ngay': ngay,
                'dia_chi': dong.o, 'nhan': dong.name,
                'tri_tho': str(gt)[:120],
                'tri': tri if isinstance(tri, (int, float)) else 0.0,
                # Chỉ ghi dạng chữ khi trị KHÔNG phải số. Ghi cả hai thì
                # cột "trị ghi" lặp lại cột "trị đã đổi" ở mọi dòng số,
                # và cái lặp đó làm chìm đúng những dòng cần đọc — dòng
                # chữ, nơi bảng ánh xạ giá trị vừa đổi "Cloudy" thành
                # một mã lựa chọn.
                'tri_text': ('' if isinstance(tri, (int, float))
                             else str(tri)[:120]),
                'dich_text': self._nhan_dich(dong),
                'ly_do': (_('trị gốc × %s', dong.he_so)
                          if dong.he_so != 1 else '')})

        if thieu_bb:
            nk.append({'ket_qua': 'loi', 'sheet': ts, 'ngay': ngay,
                       'nhan': _('Sheet %s', ts),
                       'ly_do': _('thiếu ô bắt buộc: %s. Bỏ qua cả sheet — '
                                  'không ghi gì.', ', '.join(thieu_bb))})
            for d in nk_tam:
                nk.append(dict(d, ket_qua='bo_qua',
                               ly_do=_('sheet bị bỏ vì thiếu ô bắt buộc')))
            return False

        nk.extend(nk_tam)
        self._ghi_gom(gom, ngay, ts, nk, chuoi)
        for dong, tri, gt in doi_chieu:
            self._doi_chieu_mot(dong, tri, gt, ngay, ts, nk)
        return bool(gom['node'])

    def _doc_dai_gio(self, ws, ts, ngay, tron, dong, nk, gom):
        """Một dải giờ ngang và dải giá trị tương ứng → số đo theo giờ."""
        try:
            o_gio = doc_nguon.tach_vung(dong.o)
            o_tri = doc_nguon.tach_vung(dong.o2)
        except doc_nguon.LoiNguon as e:
            nk.append({'ket_qua': 'loi', 'sheet': ts, 'ngay': ngay,
                       'dia_chi': dong.o, 'nhan': dong.name,
                       'ly_do': str(e)})
            return
        mui = self._mui_gio()
        nhan = 0
        for og, ot in zip(o_gio, o_tri):
            g = doc_nguon.ra_gio(doc_nguon.doc_o(ws, og, tron)[0])
            v = doc_nguon.ra_so(doc_nguon.doc_o(ws, ot, tron)[0])
            if g is None or v is None:
                continue
            dp = datetime.combine(ngay, datetime.min.time()) \
                + timedelta(hours=g)
            gom['tag'].append((dong.tag_code.strip(), self._ve_utc(dp, mui),
                               v * dong.he_so))
            nhan += 1
        nk.append({
            'ket_qua': 'ghi' if nhan else 'bo_qua', 'sheet': ts,
            'ngay': ngay, 'dia_chi': '%s / %s' % (dong.o, dong.o2),
            'nhan': dong.name, 'dich_text': self._nhan_dich(dong),
            'tri': float(nhan),
            'ly_do': _('%(n)d mốc giờ, đọc theo múi giờ %(tz)s rồi quy về '
                       'UTC', n=nhan, tz=self.template_id.tz or 'UTC')})

    def _mui_gio(self):
        try:
            return pytz.timezone((self.template_id.tz or 'UTC').strip())
        except Exception:
            return pytz.UTC

    def _ve_utc(self, dp, mui):
        """Giờ địa phương → UTC không mang tzinfo (dạng Odoo lưu).

        Giờ trong tệp là giờ ĐỊA PHƯƠNG. Đọc nó như UTC là dịch cả đường
        cong 7 tiếng: biểu đồ vẫn mượt, đỉnh bức xạ rơi vào 5 giờ sáng,
        và không ai nhìn biểu đồ mà nghĩ tới múi giờ.
        """
        try:
            return mui.localize(dp).astimezone(pytz.UTC).replace(tzinfo=None)
        except Exception:
            return dp

    # ------------------------------------------------------------------
    def _doi_tri(self, dong, gt, ts, ngay, nk):
        """Trị thô → trị ghi được, theo kiểu của trường đích."""
        ttype = dong.field_id.ttype if dong.field_id else 'float'
        if dong.dich in ('node', 'tag'):
            ttype = 'float'

        if ttype in ('float', 'integer'):
            so = doc_nguon.ra_so(gt)
            if so is None:
                nk.append({'ket_qua': 'loi', 'sheet': ts, 'ngay': ngay,
                           'dia_chi': dong.o, 'nhan': dong.name,
                           'tri_tho': str(gt)[:120],
                           'dich_text': self._nhan_dich(dong),
                           'ly_do': _('đích là số nhưng ô chứa "%s"',
                                      str(gt)[:60])})
                return None
            return so * dong.he_so

        if ttype == 'selection':
            bd = dong._ban_do_tri()
            khoa = str(gt).strip().lower()
            if khoa in bd:
                return bd[khoa]
            hop_le = self._tri_hop_le(dong)
            if str(gt).strip() in hop_le:
                return str(gt).strip()
            nk.append({
                'ket_qua': 'bo_qua', 'sheet': ts, 'ngay': ngay,
                'dia_chi': dong.o, 'nhan': dong.name,
                'tri_tho': str(gt)[:120],
                'dich_text': self._nhan_dich(dong),
                'ly_do': _('giá trị "%(v)s" chưa có trong bảng ánh xạ của '
                           'dòng mẫu. Trị hợp lệ: %(h)s.',
                           v=str(gt)[:60], h=', '.join(hop_le))})
            return None

        if ttype == 'boolean':
            return str(gt).strip().lower() in ('1', 'true', 'x', 'yes', 'có',
                                               'co', 'y')
        return str(gt).strip()

    def _tri_hop_le(self, dong):
        try:
            sel = self.env[dong.field_id.model]._fields[
                dong.field_id.name].selection
            if callable(sel):
                sel = sel(self.env[dong.field_id.model])
            return [v for v, _l in sel]
        except Exception:                                # pragma: no cover
            return []

    def _xep_vao_gom(self, dong, tri, gom, ngay):
        if dong.dich == 'weather':
            gom['weather'][dong.field_id.name] = tri
        elif dong.dich == 'kpi':
            gom['kpi'][dong.field_id.name] = tri
        elif dong.dich == 'node':
            gom['node'][dong.node_code.strip()] = (tri, dong.nguon_so)
        elif dong.dich == 'tag':
            gom['tag'].append((dong.tag_code.strip(),
                               datetime.combine(ngay, datetime.min.time()),
                               tri))

    def _nhan_dich(self, dong):
        ten = dict(DICH).get(dong.dich, dong.dich)
        chi_tiet = (dong.field_id.name if dong.field_id
                    else dong.node_code or dong.tag_code or '')
        nhan = '%s · %s' % (ten, chi_tiet) if chi_tiet else ten
        return _('%s (chỉ đối chiếu)', nhan) if dong.chi_doi_chieu else nhan

    # ------------------------------------------------------------------
    def _ghi_gom(self, gom, ngay, ts, nk, chuoi):
        """Ghi theo thứ tự ĐÍCH, không theo thứ tự dòng người khai gõ.

        Khí tượng phải vào trước hiệu suất: tổng xạ và nhiệt độ mô-đun
        trên bản ghi hiệu suất là trường *liên kết* lấy từ khí tượng. Thứ
        tự đúng không nên phụ thuộc vào việc người khai có biết luật đó
        hay không.
        """
        khoa = {'plant_id': self.plant_id.id, 'date': ngay}
        nguon_van = _('nạp từ tệp "%(f)s" theo mẫu "%(m)s"',
                      f=self.filename or '?', m=self.template_id.name)

        if gom['weather']:
            W = self.env['eam.solar.weather']
            vals = dict(gom['weather'])
            # Nạp từ tệp là MÁY lấy số, nên đánh dấu nguồn là máy; và ghi
            # lại lấy từ đâu, vì tổng xạ là mẫu số của tỷ số hiệu suất và
            # sáu tháng sau không ai nhớ con số đó ở đâu ra.
            vals.setdefault('nguon', 'may')
            vals.setdefault('irr_source', nguon_van)
            rec = W.search([('plant_id', '=', self.plant_id.id),
                            ('date', '=', ngay)], limit=1)
            if rec:
                rec.with_context(tu_so_do=True).write(vals)
            else:
                W.with_context(tu_so_do=True).create(dict(khoa, **vals))

        if gom['kpi']:
            K = self.env['eam.solar.kpi']
            rec = K.search([('plant_id', '=', self.plant_id.id),
                            ('date', '=', ngay)], limit=1)
            if rec:
                rec.write(gom['kpi'])
            else:
                K.create(dict(khoa, **gom['kpi']))

        if gom['node']:
            self._ghi_bac(gom['node'], ngay, ts, nk, chuoi)

        if gom['tag']:
            self._ghi_tag(gom['tag'], ts, ngay, nk)

    def _ghi_bac(self, theo_ma, ngay, ts, nk, chuoi):
        N, D = self.env['eam.chain.node'], self.env['eam.chain.day']
        if not chuoi:
            nk.append({'ket_qua': 'loi', 'sheet': ts, 'ngay': ngay,
                       'nhan': _('Bậc đo'),
                       'ly_do': _('nhà máy "%s" chưa khai chuỗi điểm đo nào '
                                  '— không có bậc để ghi vào.',
                                  self.plant_id.name)})
            return
        for ma, (tri, nguon) in theo_ma.items():
            bac = N.search([('chain_id', '=', chuoi.id), ('code', '=', ma)],
                           limit=1)
            if not bac:
                nk.append({
                    'ket_qua': 'loi', 'sheet': ts, 'ngay': ngay,
                    'nhan': _('Bậc %s', ma), 'tri': tri,
                    'ly_do': _('chuỗi "%(c)s" không có bậc mã "%(m)s". Mã '
                               'đang có: %(d)s.', c=chuoi.name, m=ma,
                               d=', '.join(
                                   c for c in chuoi.node_ids.mapped('code')
                                   if c))})
                continue
            cu = D.search([('node_id', '=', bac.id), ('date', '=', ngay)],
                          limit=1)
            if cu:
                cu.write({'energy': tri, 'nguon': nguon})
            else:
                D.create({'node_id': bac.id, 'date': ngay, 'energy': tri,
                          'nguon': nguon})

    def _ghi_tag(self, so_do, ts, ngay, nk):
        kq = self.env['eam.historian'].nap(list(so_do))
        if kq.get('bo_qua'):
            ly_do = {}
            for i, r in kq['bo_qua']:
                ly_do[r] = ly_do.get(r, 0) + 1
            nk.append({
                'ket_qua': 'loi', 'sheet': ts or '', 'ngay': ngay or False,
                'nhan': _('Kho chuỗi thời gian'),
                'tri': float(len(kq['bo_qua'])),
                'ly_do': _('kho từ chối %(n)d số đo: %(d)s',
                           n=len(kq['bo_qua']),
                           d='; '.join('%s (×%d)' % (k, v)
                                       for k, v in ly_do.items()))})
        if kq.get('co_chat_luong'):
            nk.append({
                'ket_qua': 'canh_bao', 'sheet': ts or '',
                'ngay': ngay or False, 'nhan': _('Kho chuỗi thời gian'),
                'tri': float(kq['co_chat_luong']),
                'ly_do': _('%d số đo vào kho kèm cờ chất lượng — xem luật '
                           'làm sạch của điểm đo.', kq['co_chat_luong'])})

    # ------------------------------------------------------------------
    def _doi_chieu_mot(self, dong, tri, gt, ngay, ts, nk):
        """So con số nhà máy tự tính với con số hệ tính ra.

        Đây là chỗ tờ báo cáo kiểm lại công thức của ta. Chạy SAU khi
        ghi, nên con số của hệ là con số vừa tính từ chính dữ liệu của
        ngày đó — không phải số cũ còn nằm lại từ lần trước.
        """
        rec = None
        if dong.dich == 'weather':
            rec = self.env['eam.solar.weather'].search(
                [('plant_id', '=', self.plant_id.id), ('date', '=', ngay)],
                limit=1)
        elif dong.dich == 'kpi':
            rec = self.env['eam.solar.kpi'].search(
                [('plant_id', '=', self.plant_id.id), ('date', '=', ngay)],
                limit=1)
        elif dong.dich == 'node':
            rec = self.env['eam.chain.day'].search(
                [('plant_id', '=', self.plant_id.id), ('date', '=', ngay),
                 ('node_id.code', '=', (dong.node_code or '').strip())],
                limit=1)
        if not rec:
            nk.append({
                'ket_qua': 'bo_qua', 'sheet': ts, 'ngay': ngay,
                'dia_chi': dong.o, 'nhan': dong.name,
                'tri': tri if isinstance(tri, (int, float)) else 0.0,
                'dich_text': self._nhan_dich(dong),
                'ly_do': _('chưa có bản ghi tương ứng để đối chiếu')})
            return

        ten_truong = dong.field_id.name if dong.field_id else 'energy'
        cua_ta = rec[ten_truong]
        if not isinstance(tri, (int, float)) or \
                not isinstance(cua_ta, (int, float)):
            khop, lech = str(tri) == str(cua_ta), 0.0
        elif cua_ta:
            lech = 100.0 * (tri - cua_ta) / cua_ta
            khop = abs(lech) <= (dong.sai_so or 0.0)
        else:
            # Hệ chưa tính ra gì mà tệp có số: không phải "lệch 0%".
            lech = 0.0 if not tri else 100.0
            khop = not tri
        nk.append({
            'ket_qua': 'khop' if khop else 'lech',
            'sheet': ts, 'ngay': ngay, 'dia_chi': dong.o, 'nhan': dong.name,
            'tri_tho': str(gt)[:120],
            'tri': tri if isinstance(tri, (int, float)) else 0.0,
            'tri_ta': cua_ta if isinstance(cua_ta, (int, float)) else 0.0,
            'lech_pct': lech,
            'dich_text': self._nhan_dich(dong),
            'ly_do': (_('khớp trong sai số %s%%', dong.sai_so) if khop else
                      _('tệp nói %(a)s, hệ tính ra %(b)s — lệch %(c).3f%%. '
                        'Đây là chỗ công thức của ta và của nhà máy chưa '
                        'gặp nhau.', a=tri, b=cua_ta, c=lech))})

    # ------------------------------------------------------------------
    # Bảng
    # ------------------------------------------------------------------
    def _chay_bang(self, nd, nk, ngay_da_doc):
        mau = self.template_id
        tieu_de, dong_tep = doc_nguon.doc_bang(nd, self.filename)
        chi_so = {t.strip().lower(): i for i, t in enumerate(tieu_de) if t}

        ct = (mau.cot_thoi_diem or '').strip().lower()
        if ct not in chi_so:
            nk.append({'ket_qua': 'loi', 'nhan': _('Cột thời điểm'),
                       'dia_chi': mau.cot_thoi_diem,
                       'ly_do': _('tệp không có cột "%(a)s". Tệp có: %(b)s.',
                                  a=mau.cot_thoi_diem,
                                  b=', '.join(t for t in tieu_de if t))})
            return
        i_ts = chi_so[ct]

        cot_dong = []
        for dong in mau.map_ids:
            k = (dong.cot or '').strip().lower()
            if dong.dich != 'tag':
                nk.append({
                    'ket_qua': 'loi', 'nhan': dong.name, 'dia_chi': dong.cot,
                    'ly_do': _('tệp bảng là chuỗi thời gian, nên đích phải '
                               'là điểm đo. Dòng này trỏ tới %s.',
                               dict(DICH).get(dong.dich))})
                continue
            if k not in chi_so:
                nk.append({
                    'ket_qua': 'loi', 'nhan': dong.name, 'dia_chi': dong.cot,
                    'dich_text': self._nhan_dich(dong),
                    'ly_do': _('tệp không có cột "%(a)s". Tệp có: %(b)s.',
                               a=dong.cot,
                               b=', '.join(t for t in tieu_de if t))})
                continue
            cot_dong.append((chi_so[k], dong))
        if not cot_dong:
            return

        mui = self._mui_gio()
        so_do, bo_ts = [], 0
        dem_cot = {d.id: 0 for i, d in cot_dong}
        for d in dong_tep:
            if i_ts >= len(d):
                bo_ts += 1
                continue
            dp = self._doc_thoi_diem(d[i_ts], mui)
            if dp is None:
                bo_ts += 1
                continue
            ngay_da_doc.add(dp.date())
            for i, dong in cot_dong:
                if i >= len(d):
                    continue
                v = doc_nguon.ra_so(d[i])
                if v is None:
                    continue
                so_do.append((dong.tag_code.strip(), dp, v * dong.he_so))
                dem_cot[dong.id] += 1

        if bo_ts:
            nk.append({
                'ket_qua': 'canh_bao', 'nhan': _('Cột thời điểm'),
                'dia_chi': mau.cot_thoi_diem, 'tri': float(bo_ts),
                'ly_do': _('%d dòng không đọc được thời điểm nên bị bỏ. '
                           'Thường là dòng tổng ở cuối tệp hoặc dòng '
                           'trống.', bo_ts)})
        if so_do:
            self._ghi_tag(so_do, '', None, nk)
        for i, dong in cot_dong:
            n = dem_cot[dong.id]
            nk.append({
                'ket_qua': 'ghi' if n else 'bo_qua', 'nhan': dong.name,
                'dia_chi': dong.cot, 'dich_text': self._nhan_dich(dong),
                'tri': float(n),
                'ly_do': _('%(n)d số đo, đọc theo múi giờ %(tz)s rồi quy về '
                           'UTC%(h)s', n=n, tz=mau.tz or 'UTC',
                           h=(_('; × hệ số %s', dong.he_so)
                              if dong.he_so != 1 else ''))})

    def _doc_thoi_diem(self, gt, mui):
        """Ô thời điểm → datetime UTC không mang tzinfo (dạng Odoo lưu)."""
        if isinstance(gt, datetime):
            dp = gt
        else:
            dp = None
            s = str(gt or '').strip()
            for d in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M',
                      '%d/%m/%Y %H:%M:%S', '%d/%m/%Y %H:%M',
                      '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M',
                      '%Y-%m-%d'):
                try:
                    dp = datetime.strptime(s, d)
                    break
                except ValueError:
                    continue
            if dp is None:
                return None
        if dp.tzinfo is not None:
            return dp.astimezone(pytz.UTC).replace(tzinfo=None)
        return self._ve_utc(dp, mui)


class EamImportLog(models.Model):
    _name = 'eam.import.log'
    _description = 'Nhật ký nạp dữ liệu'
    _order = 'run_id, id'

    run_id = fields.Many2one(
        'eam.import.run', string='Lượt nạp', required=True,
        ondelete='cascade', index=True)
    sheet = fields.Char(string='Sheet')
    ngay = fields.Date(string='Ngày')
    dia_chi = fields.Char(string='Ô / cột')
    nhan = fields.Char(string='Nhãn trong tệp')
    dich_text = fields.Char(string='Đích')

    tri_tho = fields.Char(string='Trị gốc trong tệp')
    tri = fields.Float(string='Trị đã đổi', digits=(16, 4), aggregator=False)
    tri_text = fields.Char(string='Trị ghi')
    tri_ta = fields.Float(string='Hệ tính ra', digits=(16, 4),
                          aggregator=False)
    lech_pct = fields.Float(string='Lệch (%)', digits=(8, 3),
                            aggregator=False)

    ket_qua = fields.Selection(KET_QUA, string='Kết quả', required=True,
                               default='ghi', index=True)
    ly_do = fields.Text(string='Lý do')
