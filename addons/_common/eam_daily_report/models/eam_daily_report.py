# -*- coding: utf-8 -*-
"""Tờ báo cáo vận hành ngày: máy rót sẵn, người trực sửa chừng mười ô.

Báo cáo ngày KHÔNG tính lại gì cả
----------------------------------
Mọi con số của một ngày đã nằm sẵn trong hệ: khí tượng ở sổ quan trắc,
sản lượng từng bậc ở chuỗi điểm đo, hiệu suất ở bảng PR, khả dụng ở sổ
khả dụng, giờ dừng ở sổ dừng máy. Tờ báo cáo là lớp **lắp ráp**, không
phải engine thứ hai — có engine thứ hai là có hai con số cho cùng một
ngày, và cuộc họp sau đó bàn xem tin cái nào.

Chốt là CHỤP LẠI, không phải khoá đọc tiếp
-------------------------------------------
Một tờ báo cáo ngày là bản ghi **những gì đã báo hôm đó**. Nếu nó vẫn
đọc thẳng từ các bảng nguồn thì mở lại sau ba tháng sẽ ra số khác —
người ta đã sửa một khoảng dừng, đã nạp lại một tệp SCADA — và tờ báo
cáo **tự lật ngược chính nó** mà không ai biết nó từng nói gì. Nên lúc
chốt, giá trị được chép vào từng dòng và đứng yên ở đó.

Cùng bài học đã trả giá ở ảnh chụp bảo hành trên phiếu RMA, ở kỳ hợp
đồng O&M, và ở sơ đồ nhà máy chụp lúc mở ca.

Không đo được thì NÓI, không ghi 0
-----------------------------------
Ô trống và số không là hai chuyện khác hẳn nhau: *chưa có số đo* khác
*đo được và bằng không*. Ghi 0 cho cái chưa đo được thì tổng vẫn cộng
ra, biểu đồ vẫn vẽ, và không ai biết hôm đó mất dữ liệu. Nên mỗi dòng
mang cờ ``do_duoc`` kèm lý do, và bản in ghi "—" chứ không ghi "0".

Sửa sau khi chốt thì ra BẢN MỚI
--------------------------------
Số liệu ngày hôm qua có thể đúng là phải sửa — SCADA nạp lại, một
khoảng dừng khai nhầm nhóm. Nhưng sửa đè lên tờ đã gửi đi là xoá mất
chuyện "hôm đó ta đã báo thế này". Nên sửa sinh ra bản kế tiếp, trỏ
ngược về bản cũ, và bản cũ chuyển sang "đã thay thế" chứ không biến
mất.
"""
import logging
from datetime import datetime, time, timedelta

import pytz

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .eam_daily_profile import KHOI

_logger = logging.getLogger(__name__)

#: Bảng nguồn của từng loại nguồn, để tra tên trường khi khai sai.
BANG_NGUON = {
    'weather': 'eam.solar.weather',
    'kpi': 'eam.solar.kpi',
    'avail': 'eam.availability.day',
    'chain': 'eam.chain.day',
}


class EamDailyReport(models.Model):
    _name = 'eam.daily.report'
    _description = 'Báo cáo vận hành ngày'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, plant_id, ban_so desc'
    _rec_name = 'display_name'

    plant_id = fields.Many2one(
        'eam.location', string='Nhà máy', required=True, index=True,
        domain="[('location_type', '=', 'plant')]", tracking=True)
    date = fields.Date(string='Ngày', required=True, index=True,
                       default=lambda s: fields.Date.context_today(s) -
                       timedelta(days=1), tracking=True)
    profile_id = fields.Many2one(
        'eam.daily.profile', string='Hồ sơ cấu hình', required=True,
        tracking=True,
        help='Quyết định tờ này có những dòng nào và mỗi dòng lấy số từ '
             'đâu. Đổi hồ sơ sau khi đã rót số thì phải rót lại.')
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda s: s.env.company)
    state = fields.Selection(
        [('nhap', 'Nháp'), ('chot', 'Đã chốt'),
         ('thay_the', 'Đã thay thế')],
        string='Trạng thái', default='nhap', required=True, index=True,
        tracking=True, copy=False)

    line_ids = fields.One2many(
        'eam.daily.report.line', 'report_id', string='Dòng', copy=False)
    # One2many mặc định copy=False, nên phải khai rõ ở chỗ nào cần chép.

    # ----- Vết bản ----------------------------------------------------
    ban_so = fields.Integer(string='Bản số', default=1, readonly=True,
                            copy=False)
    nguon_id = fields.Many2one(
        'eam.daily.report', string='Sửa từ bản', readonly=True, copy=False,
        ondelete='set null')
    ban_sau_id = fields.Many2one(
        'eam.daily.report', string='Đã thay bằng bản', readonly=True,
        copy=False, ondelete='set null')
    ly_do_sua = fields.Char(string='Lý do sửa', readonly=True, copy=False)

    mui_gio = fields.Char(
        string='Múi giờ đã dùng', readonly=True, copy=False,
        help='CHỤP LẠI lúc tạo tờ. Biên ngày thuộc về nhà máy, không '
             'thuộc người đang mở màn hình — không chụp thì cùng một tờ '
             'rót lại từ máy khác sẽ ra số khác mà không gì báo.')

    nguoi_chot_id = fields.Many2one('res.users', string='Người chốt',
                                    readonly=True, copy=False)
    ngay_chot = fields.Datetime(string='Chốt lúc', readonly=True,
                                copy=False)

    # ----- Khối hoạt động: máy dựng câu, người sửa câu chữ -------------
    hoat_dong = fields.Html(
        string='Hoạt động trong ngày',
        help='Máy dựng sẵn từ lệnh công việc và sổ dừng máy trong ngày. '
             'Người trực sửa câu chữ, không phải gõ lại từ đầu.')
    hoat_dong_da_sua = fields.Boolean(
        string='Người đã sửa khối hoạt động', readonly=True, copy=False,
        help='Dựng lại sẽ ĐÈ mất phần đã sửa, nên hệ hỏi trước.')

    # ----- Số tóm tắt, để lọc và xếp hạng ------------------------------
    sl_ban = fields.Float(
        string='Sản lượng bán (kWh)', digits=(16, 1), readonly=True,
        copy=False,
        help='Lấy từ dòng gắn với bậc đo bán điện. Chép ra đây để lọc và '
             'cộng được — dòng trong bảng con thì không.')
    so_o_trong = fields.Integer(
        string='Ô người trực còn trống', compute='_compute_kiem',
        store=True)
    so_chua_do = fields.Integer(
        string='Dòng chưa có số đo', compute='_compute_kiem', store=True)
    thieu_bat_buoc = fields.Boolean(
        string='Còn ô bắt buộc để trống', compute='_compute_kiem',
        store=True)

    display_name = fields.Char(compute='_compute_display_name',
                               store=True)

    _ngay_uniq = models.Constraint(
        'unique(plant_id, date, ban_so, company_id)',
        'Nhà máy này đã có bản báo cáo cùng số cho ngày đó rồi.')

    # ==================================================================
    @api.depends('plant_id', 'date', 'ban_so')
    def _compute_display_name(self):
        for r in self:
            ten = '%s — %s' % (r.plant_id.name or '', r.date or '')
            r.display_name = ten if r.ban_so <= 1 else _(
                '%(t)s (bản %(n)d)', t=ten, n=r.ban_so)

    @api.depends('line_ids.gia_tri', 'line_ids.gia_tri_chu',
                 'line_ids.do_duoc', 'line_ids.nguon', 'line_ids.bat_buoc',
                 'line_ids.ghi_nguoc')
    def _compute_kiem(self):
        for r in self:
            # Ô ghi ngược CŨNG là ô người trực phải điền — nó chỉ khác ở
            # chỗ ghi vào bảng nào. Đếm thiếu nó thì con số "còn mấy ô"
            # nói dối đúng cái phần người ta dựa vào để biết xong chưa.
            nguoi = r.line_ids.filtered(
                lambda l: l.nguon == 'nguoi' or l.ghi_nguoc)
            trong = nguoi.filtered(lambda l: l.trong())
            r.so_o_trong = len(trong)
            r.so_chua_do = len(r.line_ids.filtered(
                lambda l: l.nguon != 'nguoi' and not l.ghi_nguoc
                and not l.do_duoc))
            r.thieu_bat_buoc = bool(trong.filtered('bat_buoc'))

    @api.onchange('plant_id')
    def _onchange_plant(self):
        """Đoán hồ sơ theo loại nhà máy — đoán thôi, người vẫn đổi được."""
        if not self.plant_id or self.profile_id:
            return
        loai = 'pv' if self.plant_id.is_solar else 'wind'
        self.profile_id = self.env['eam.daily.profile'].search(
            [('loai', '=', loai)], limit=1)

    # ==================================================================
    # Dựng dòng & rót số
    # ==================================================================
    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for r in recs:
            if not r.mui_gio:
                r.mui_gio = r.plant_id.mui_gio()
            if not r.line_ids:
                r._dung_dong()
                r._rot_so()
                r._dung_hoat_dong()
        return recs

    def _dung_dong(self):
        """Dựng dòng từ hồ sơ cấu hình. Chỉ khi còn nháp."""
        self.ensure_one()
        if self.state != 'nhap':
            raise UserError(_('Tờ đã chốt thì không dựng lại dòng được.'))
        self.line_ids.unlink()
        self.env['eam.daily.report.line'].create([{
            'report_id': self.id,
            'profile_line_id': l.id,
            'sequence': l.sequence,
        } for l in self.profile_id.line_ids])

    def action_rot_lai(self):
        """Rót lại số máy tính — giữ nguyên ô người trực đã điền."""
        for r in self:
            if r.state != 'nhap':
                raise UserError(_(
                    'Tờ ngày %s đã chốt. Số đã chốt là bản ghi của hôm '
                    'đó, không rót đè lên được — muốn đổi thì bấm "Sửa '
                    'ra bản mới".', r.date))
            r._rot_so()
        return self._bao(_('Đã rót lại số cho %d tờ.', len(self)))

    def _mui_gio(self):
        self.ensure_one()
        return self.mui_gio or self.plant_id.mui_gio()

    def _bien_ngay_utc(self):
        """Biên ngày theo múi giờ NHÀ MÁY, đổi sang UTC, HẾT là hở.

        Ngày 19/10 của nhà máy là 00:00 19/10 tới 00:00 20/10 giờ địa
        phương. Lấy ``den.date()`` rồi so sánh theo ngày là nuốt luôn cả
        ngày hôm sau — đã dính đúng thế ở khả dụng theo sản lượng, và
        con số chênh chỉ lộ ra khi đem cộng tay.
        """
        self.ensure_one()
        mui = pytz.timezone(self._mui_gio())
        dau = mui.localize(datetime.combine(self.date, time.min))
        return (dau.astimezone(pytz.UTC).replace(tzinfo=None),
                (dau + timedelta(days=1)).astimezone(pytz.UTC)
                .replace(tzinfo=None))

    def _ban_ghi_nguon(self, nguon, tao_neu_thieu=False):
        """Bản ghi của NGÀY này trên bảng nguồn, tạo nếu được phép.

        Ô ghi ngược cần một bản ghi để ghi vào. Nhà máy không nạp tệp
        thì sổ quan trắc chưa có dòng nào cho hôm đó — tạo dòng rỗng khi
        người trực điền ô đầu tiên là đúng, vì chính họ là nguồn.
        """
        self.ensure_one()
        mo = BANG_NGUON.get(nguon)
        if not mo or mo not in self.env:
            return None
        M = self.env[mo]
        bg = M.search([('plant_id', '=', self.plant_id.id),
                       ('date', '=', self.date)], limit=1)
        if not bg and tao_neu_thieu:
            v = {'plant_id': self.plant_id.id, 'date': self.date}
            if 'nguon' in M._fields:
                v['nguon'] = 'tay'
            bg = M.create(v)
        return bg

    def _rot_so(self):
        """Rót số vào từng dòng không-phải-người-nhập.

        Không tính gì ở đây. Mỗi nhánh chỉ đi tìm bản ghi của đúng ngày
        đó rồi lấy một trường — không đo được thì ghi LÝ DO, không ghi 0.
        """
        self.ensure_one()
        tu, den = self._bien_ngay_utc()
        ctx = {
            'tu': tu, 'den': den,
            'weather': self.env['eam.solar.weather'].search([
                ('plant_id', '=', self.plant_id.id),
                ('date', '=', self.date)], limit=1),
            'kpi': self.env['eam.solar.kpi'].search([
                ('plant_id', '=', self.plant_id.id),
                ('date', '=', self.date)], limit=1),
            'avail': self.env['eam.availability.day'].search([
                ('plant_id', '=', self.plant_id.id),
                ('date', '=', self.date)], limit=1),
            'dung': None,
        }
        for l in self.line_ids.filtered(lambda x: x.nguon != 'nguoi'):
            l._rot(ctx)
        self._cap_nhat_tom_tat()

    def _cap_nhat_tom_tat(self):
        self.ensure_one()
        ban = self.line_ids.filtered(
            lambda l: l.nguon == 'chain' and l.profile_line_id.node_code
            and l.do_duoc and l.la_san_luong_ban())
        self.sl_ban = ban[:1].gia_tri or 0.0

    # ==================================================================
    # Khối hoạt động
    # ==================================================================
    def action_dung_hoat_dong(self):
        for r in self:
            if r.state != 'nhap':
                raise UserError(_('Tờ đã chốt thì không dựng lại được.'))
            if r.hoat_dong_da_sua:
                raise UserError(_(
                    'Khối hoạt động của tờ ngày %s đã được sửa tay. Dựng '
                    'lại sẽ ĐÈ mất phần đã sửa. Xoá nội dung trong ô rồi '
                    'bấm lại nếu đúng là muốn dựng từ đầu.', r.date))
            r._dung_hoat_dong()
        return True

    def _dung_hoat_dong(self):
        """Dựng câu từ lệnh công việc và khoảng dừng TRONG NGÀY.

        Người trực sửa câu chữ; máy lo phần không được quên. Việc hay bị
        quên nhất trong một tờ viết tay là khoảng dừng ngắn — nó không
        gây ấn tượng gì lúc trực, nhưng cuối tháng cộng lại mới thấy.
        """
        self.ensure_one()
        tu, den = self._bien_ngay_utc()
        phan = []

        O = self.env['eam.outage'].search([
            ('location_id', 'child_of', self.plant_id.id),
            ('state', '=', 'confirmed'), ('is_root_cause', '=', False),
            ('date_start', '<', den),
            '|', ('date_end', '=', False), ('date_end', '>', tu)])
        if O:
            muc = ['<p><b>%s</b></p><ul>' % _('Dừng máy')]
            for o in O.sorted('date_start'):
                muc.append('<li>%s</li>' % _(
                    '%(vt)s — %(ly)s, từ %(a)s%(b)s',
                    vt=o.location_id.complete_code or o.location_id.name,
                    ly=(o.category_id.name or o.reason or _('chưa phân loại')),
                    a=fields.Datetime.to_string(o.date_start),
                    b='' if o.date_end else _(' (CHƯA kết thúc)')))
            muc.append('</ul>')
            phan.append(''.join(muc))

        W = self.env['eam.work.order'].search([
            ('location_id', 'child_of', self.plant_id.id),
            '|', '&', ('date_start', '>=', tu), ('date_start', '<', den),
            '&', ('date_end', '>=', tu), ('date_end', '<', den)])
        if W:
            muc = ['<p><b>%s</b></p><ul>' % _('Công việc bảo trì')]
            for w in W.sorted('date_start'):
                muc.append('<li>%s — %s</li>' % (
                    w.display_name,
                    dict(w._fields['state'].selection).get(w.state,
                                                           w.state)))
            muc.append('</ul>')
            phan.append(''.join(muc))

        if not phan:
            phan.append('<p><i>%s</i></p>' % _(
                'Không có khoảng dừng hay lệnh công việc nào được ghi '
                'nhận trong ngày. Đây là điều hệ ĐỌC ĐƯỢC, không phải '
                'lời khẳng định rằng không có gì xảy ra.'))
        self.hoat_dong = ''.join(phan)
        self.hoat_dong_da_sua = False

    def write(self, vals):
        if 'hoat_dong' in vals and not self.env.context.get('may_dung'):
            vals.setdefault('hoat_dong_da_sua', True)
        return super().write(vals)

    # ==================================================================
    # Chốt & sửa
    # ==================================================================
    def action_chot(self):
        for r in self:
            if r.state != 'nhap':
                raise UserError(_('Tờ ngày %s không còn ở nháp.', r.date))
            if r.thieu_bat_buoc:
                thieu = r.line_ids.filtered(
                    lambda l: (l.nguon == 'nguoi' or l.ghi_nguoc)
                    and l.bat_buoc and l.trong())
                raise UserError(_(
                    'Còn %(n)d ô bắt buộc để trống: %(ds)s.\n\nĐể trống '
                    'những ô này thì tờ báo cáo mất nghĩa — chúng được '
                    'đánh dấu bắt buộc chính vì thế.',
                    n=len(thieu),
                    ds=', '.join(thieu.mapped('name'))))
            r.write({
                'state': 'chot',
                'nguoi_chot_id': self.env.user.id,
                'ngay_chot': fields.Datetime.now(),
            })
            # Dòng chụp lại là đủ: giá trị đã nằm trên từng dòng từ lúc
            # rót. Việc của chốt là CẤM rót đè, không phải chép thêm lần
            # nữa.
            r.message_post(body=_(
                'Đã chốt bản %(n)d. %(a)d dòng chưa có số đo, %(b)d ô '
                'người trực để trống.',
                n=r.ban_so, a=r.so_chua_do, b=r.so_o_trong))
        return True

    def action_mo_lai(self):
        """Mở lại — chỉ cho bản chưa gửi đi, và chỉ người chốt hoặc quản lý."""
        for r in self:
            if r.state != 'chot':
                raise UserError(_('Tờ này không ở trạng thái đã chốt.'))
            r.write({'state': 'nhap', 'nguoi_chot_id': False,
                     'ngay_chot': False})
            r.message_post(body=_('Mở lại bản %d để sửa.', r.ban_so))
        return True

    def action_sua_lai(self):
        """Sinh bản kế tiếp, giữ nguyên bản cũ làm vết."""
        self.ensure_one()
        if self.state != 'chot':
            raise UserError(_(
                'Chỉ bản ĐÃ CHỐT mới cần sinh bản mới. Bản còn nháp thì '
                'sửa thẳng.'))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'eam.daily.revise.wizard',
            'view_mode': 'form', 'target': 'new',
            'name': _('Sửa ra bản mới'),
            'context': {'default_report_id': self.id},
        }

    def _sinh_ban_moi(self, ly_do):
        self.ensure_one()
        moi = self.copy({
            'ban_so': self.ban_so + 1,
            'nguon_id': self.id,
            'ly_do_sua': ly_do,
            'state': 'nhap',
            'hoat_dong': self.hoat_dong,
            'hoat_dong_da_sua': self.hoat_dong_da_sua,
        })
        # Chép giá trị người trực đã điền sang bản mới: bắt gõ lại là
        # mời sai khác vào giữa hai bản của cùng một ngày.
        cu = {l.profile_line_id.id: l for l in self.line_ids}
        for l in moi.line_ids:
            g = cu.get(l.profile_line_id.id)
            if g and (g.nguon == 'nguoi' or g.ghi_nguoc):
                l.write({'gia_tri': g.gia_tri,
                         'gia_tri_chu': g.gia_tri_chu,
                         'do_duoc': g.do_duoc})
        moi._rot_so()
        self.write({'state': 'thay_the', 'ban_sau_id': moi.id})
        self.message_post(body=_(
            'Thay bằng bản %(n)d. Lý do: %(l)s', n=moi.ban_so, l=ly_do))
        moi.message_post(body=_(
            'Sinh từ bản %(n)d. Lý do: %(l)s', n=self.ban_so, l=ly_do))
        return moi

    def unlink(self):
        if any(r.state == 'chot' for r in self):
            raise UserError(_(
                'Không xoá được tờ đã chốt. Tờ đã chốt là bản ghi của '
                'những gì đã báo hôm đó — sửa thì sinh bản mới, xoá thì '
                'mất luôn chuyện đã từng báo.'))
        return super().unlink()

    # ==================================================================
    def _khoi_in(self):
        """Khối nào có dòng, theo đúng thứ tự in đã khai ở hồ sơ."""
        self.ensure_one()
        co = set(self.line_ids.mapped('khoi'))
        return [{'ma': ma, 'ten': ten} for ma, ten in KHOI if ma in co]

    def _bao(self, loi_nhan, kieu='info'):
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {'type': kieu, 'message': loi_nhan, 'sticky': False},
        }

    def action_xem_ban_truoc(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'res_model': 'eam.daily.report',
            'res_id': self.nguon_id.id, 'view_mode': 'form',
        }

    # ==================================================================
    # Sinh theo lịch
    # ==================================================================
    @api.model
    def _cron_dung_bao_cao(self):
        """Sáng sớm dựng sẵn tờ của NGÀY HÔM QUA cho mọi nhà máy có hồ sơ.

        Dựng chứ KHÔNG chốt và KHÔNG gửi: tờ báo cáo cần người trực xác
        nhận quan trắc và nhận xét. Tự gửi một tờ chưa ai đọc là biến
        báo cáo ngày thành thư rác trong ba ngày.
        """
        P = self.env['eam.daily.profile']
        hom_qua = fields.Date.context_today(self) - timedelta(days=1)
        dung = 0
        for nm in self.env['eam.location'].search(
                [('location_type', '=', 'plant')]):
            loai = 'pv' if nm.is_solar else 'wind'
            hs = P.search([('loai', '=', loai)], limit=1)
            if not hs:
                continue
            if self.search_count([('plant_id', '=', nm.id),
                                  ('date', '=', hom_qua)]):
                continue
            self.create({'plant_id': nm.id, 'date': hom_qua,
                         'profile_id': hs.id})
            dung += 1
        return {'da_dung': dung}

    @api.model
    def _cron_nhac_chua_chot(self):
        """Nhắc tờ còn nháp quá một ngày — không nhắc tờ của hôm nay."""
        han = fields.Date.context_today(self) - timedelta(days=1)
        tre = self.search([('state', '=', 'nhap'), ('date', '<', han)])
        for r in tre:
            nguoi = r.plant_id.manager_id or r.create_uid
            if not nguoi:
                continue
            r.activity_schedule(
                'mail.mail_activity_data_todo', user_id=nguoi.id,
                summary=_('Báo cáo ngày chưa chốt'),
                note=_('Tờ %(t)s còn ở nháp. Còn %(a)d ô phải điền.',
                       t=r.display_name, a=r.so_o_trong))
        return {'nhac': len(tre)}


class EamDailyReviseWizard(models.TransientModel):
    _name = 'eam.daily.revise.wizard'
    _description = 'Sửa báo cáo ngày ra bản mới'

    report_id = fields.Many2one('eam.daily.report', required=True)
    ly_do = fields.Char(
        string='Lý do sửa', required=True,
        help='Ghi rõ vì sao số đổi: nạp lại SCADA, khai lại nhóm dừng… '
             'Ba tháng sau đây là thứ duy nhất giải thích vì sao cùng '
             'một ngày có hai tờ.')

    def action_tao(self):
        self.ensure_one()
        moi = self.report_id._sinh_ban_moi(self.ly_do)
        return {
            'type': 'ir.actions.act_window', 'res_model': 'eam.daily.report',
            'res_id': moi.id, 'view_mode': 'form',
        }
