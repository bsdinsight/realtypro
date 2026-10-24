# -*- coding: utf-8 -*-
"""Một dòng giá trị trên tờ báo cáo ngày.

Ô trống KHÁC số không
----------------------
*Chưa có số đo* và *đo được và bằng không* là hai chuyện khác hẳn nhau,
và chỉ có một cách phân biệt: một cờ riêng. Ghi 0 cho cái chưa đo được
thì tổng vẫn cộng ra, biểu đồ vẫn vẽ liền mạch, và không ai biết hôm đó
mất dữ liệu — cho tới lúc đối chiếu hoá đơn.

Nên mỗi dòng mang ``do_duoc`` kèm ``ly_do_chua_do``, và bản in ghi "—".
"""
import logging

import pytz

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)

#: Bảng nguồn ghi ngược được — xem _ghi_nguoc.
BANG_NGUON = ('weather',)


class EamDailyReportLine(models.Model):
    _name = 'eam.daily.report.line'
    _description = 'Dòng báo cáo ngày'
    _order = 'report_id, khoi, sequence, id'

    report_id = fields.Many2one(
        'eam.daily.report', required=True, ondelete='cascade', index=True)
    profile_line_id = fields.Many2one(
        'eam.daily.profile.line', string='Dòng cấu hình', required=True,
        ondelete='restrict')
    sequence = fields.Integer(default=10)

    # Nhãn và cách lấy số đều thuộc về CẤU HÌNH, nên lấy quan hệ chứ
    # không chép: sửa nhãn trên hồ sơ thì mọi tờ còn nháp đổi theo.
    # Giá trị thì ngược lại — chép hẳn vào dòng, vì nó là số của ngày đó.
    name = fields.Char(related='profile_line_id.name', store=True,
                       string='Nhãn')
    khoi = fields.Selection(related='profile_line_id.khoi', store=True,
                            string='Khối', index=True)
    don_vi = fields.Char(related='profile_line_id.don_vi', string='Đơn vị')
    so_le = fields.Integer(related='profile_line_id.so_le')
    kieu = fields.Selection(related='profile_line_id.kieu')
    nguon = fields.Selection(related='profile_line_id.nguon', store=True,
                             string='Nguồn')
    bat_buoc = fields.Boolean(related='profile_line_id.bat_buoc',
                              store=True)
    goi_y = fields.Char(related='profile_line_id.goi_y')
    ghi_nguoc = fields.Boolean(related='profile_line_id.ghi_nguoc',
                               store=True)
    co_the_sua = fields.Boolean(
        string='Người sửa được', compute='_compute_co_the_sua',
        help='Ô người trực, hoặc ô ghi ngược về bảng nguồn. Còn lại là '
             'máy rót và khoá — chép tay con số hệ đã có là mời sai số '
             'vào.')
    state = fields.Selection(related='report_id.state', store=True)

    gia_tri = fields.Float(string='Giá trị', digits=(16, 4),
                           aggregator=False)
    gia_tri_chu = fields.Char(string='Giá trị (chữ)')
    do_duoc = fields.Boolean(
        string='Có số đo', default=False,
        help='Bỏ trống KHÔNG phải là bằng không. Dòng không đo được vẫn '
             'ra trên bản in, kèm lý do, chứ không biến thành số 0.')
    ly_do_chua_do = fields.Char(string='Vì sao chưa có số', readonly=True)
    nguon_ghi = fields.Char(
        string='Lấy từ đâu', readonly=True,
        help='Vết: bản ghi nào đã cho con số này.')

    hien_thi = fields.Char(string='Hiển thị', compute='_compute_hien_thi')

    @api.depends('gia_tri', 'gia_tri_chu', 'do_duoc', 'so_le', 'kieu',
                 'don_vi')
    def _compute_hien_thi(self):
        for l in self:
            if not l.do_duoc:
                l.hien_thi = '—'
            elif l.kieu == 'chu':
                l.hien_thi = l.gia_tri_chu or '—'
            else:
                l.hien_thi = '{:,.{p}f}{u}'.format(
                    l.gia_tri or 0.0, p=max(l.so_le, 0),
                    u=(' ' + l.don_vi) if l.don_vi else '')

    @api.depends('nguon', 'ghi_nguoc', 'state')
    def _compute_co_the_sua(self):
        for l in self:
            l.co_the_sua = (l.state == 'nhap'
                            and (l.nguon == 'nguoi' or l.ghi_nguoc))

    def trong(self):
        """Ô người trực coi là TRỐNG khi chưa ai chạm vào."""
        self.ensure_one()
        if self.kieu == 'chu':
            return not (self.gia_tri_chu or '').strip()
        return not self.do_duoc

    def write(self, vals):
        """Ô ghi ngược thì ghi THẲNG vào bảng nguồn, không giữ bản sao.

        Giữ bản sao trên tờ là có hai nơi cùng nói một chuyện, và tới
        lúc lệch thì không ai biết bên nào mới. Ghi ngược giữ đúng một
        nhà cho dữ liệu, mà người trực vẫn chỉ mở một màn hình.
        """
        res = super().write(vals)
        if 'gia_tri' in vals or 'gia_tri_chu' in vals:
            self._tu_danh_dau_da_dien(vals)
            for l in self.filtered(lambda x: x.ghi_nguoc and
                                   x.nguon in BANG_NGUON):
                l._ghi_nguoc()
        return res

    def _tu_danh_dau_da_dien(self, vals):
        """Ô CHỮ người trực gõ: có chữ là có giá trị, khỏi gạt thêm cờ.

        Cờ ``do_duoc`` sinh ra để phân biệt *chưa đo được* với *đo được
        và bằng không* — chuyện của ô SỐ. Với ô chữ, bản thân dòng chữ
        đã là câu trả lời, và bắt người trực gõ xong còn gạt thêm một
        nút là chỗ họ sẽ quên.

        Quên thì bản in ra "—" cho ô "Sự cố an toàn trong ngày" mà người
        trực đã ghi rõ "Không" — một tờ báo cáo nói sai đúng cái ô không
        được phép nói sai.

        Ô SỐ thì KHÔNG tự suy được: nhập 0 khách và chưa đếm khách là
        hai chuyện khác nhau, và chỉ có cái nút phân biệt được.
        """
        if 'gia_tri_chu' not in vals:
            return
        for l in self.filtered(lambda x: x.nguon == 'nguoi'
                               and x.kieu == 'chu'):
            co = bool((l.gia_tri_chu or '').strip())
            if l.do_duoc != co:
                super(EamDailyReportLine, l).write({'do_duoc': co})

    def _ghi_nguoc(self):
        self.ensure_one()
        c = self.profile_line_id
        bg = self.report_id._ban_ghi_nguon(c.nguon, tao_neu_thieu=True)
        if not bg or c.truong not in bg._fields:
            return
        if c.kieu == 'chu':
            gt, loi = self._ghi_chu_vao(bg, c)
            if loi:
                return self.write({'do_duoc': False,
                                   'ly_do_chua_do': loi})
        else:
            gt = self.gia_tri / (c.he_so or 1.0)
        bg[c.truong] = gt
        self.write({
            'do_duoc': bool(gt),
            'ly_do_chua_do': False,
            'nguon_ghi': _('người trực điền, ghi vào %s',
                           bg.display_name)})

    def la_san_luong_ban(self):
        """Dòng này có trỏ vào bậc đo BÁN ĐIỆN không."""
        self.ensure_one()
        c = self.profile_line_id
        if c.nguon != 'chain' or not c.node_code:
            return False
        nut = self.env['eam.chain.node'].search([
            ('plant_id', '=', self.report_id.plant_id.id),
            ('code', '=', c.node_code)], limit=1)
        return bool(nut.is_billing)

    # ==================================================================
    def _dat(self, gt, nguon_ghi, chu=False):
        self.write({
            'gia_tri': 0.0 if chu else (gt or 0.0),
            'gia_tri_chu': gt if chu else False,
            'do_duoc': True, 'ly_do_chua_do': False,
            'nguon_ghi': nguon_ghi,
        })

    def _chua_do(self, ly_do):
        """KHÔNG ghi 0. Ghi lý do, và để ô trống."""
        self.write({'gia_tri': 0.0, 'gia_tri_chu': False,
                    'do_duoc': False, 'ly_do_chua_do': ly_do,
                    'nguon_ghi': False})

    def _rot(self, ctx):
        """Đi tìm con số của đúng ngày này, hoặc nói rõ vì sao không có."""
        self.ensure_one()
        c = self.profile_line_id
        try:
            getattr(self, '_rot_%s' % c.nguon)(ctx, c)
        except Exception as e:                       # noqa: BLE001
            # Một dòng hỏng không được làm hỏng cả tờ: ghi lý do vào
            # đúng dòng đó rồi đi tiếp. Dừng cả lượt rót vì một dòng khai
            # sai là cách chắc chắn khiến không ai dám bấm nút rót.
            _logger.exception('eam_daily_report: rót dòng %s', c.name)
            self._chua_do(_('lỗi khi lấy số: %s', str(e)[:120]))

    # ----- từng nguồn -------------------------------------------------
    def _lay_truong(self, ban_ghi, ten_truong, ten_bang):
        if not ban_ghi:
            return None, _('không có bản ghi %(b)s cho ngày này',
                           b=ten_bang)
        if ten_truong not in ban_ghi._fields:
            co = ', '.join(sorted(
                k for k, v in ban_ghi._fields.items()
                if v.type in ('float', 'integer', 'monetary'))[:12])
            return None, _('bảng %(b)s không có trường "%(t)s"; các '
                           'trường số đang có: %(c)s…',
                           b=ten_bang, t=ten_truong, c=co)
        return ban_ghi[ten_truong], None

    def _rot_weather(self, ctx, c):
        w = ctx['weather']
        gt, loi = self._lay_truong(w, c.truong, _('quan trắc'))
        if loi:
            return self._chua_do(loi)
        if c.kieu == 'chu':
            return self._dat(self._ra_chu(w, c.truong, gt),
                             w.display_name, chu=True)
        self._dat(gt * c.he_so, w.display_name)

    @api.model
    def _ra_chu(self, ban_ghi, ten_truong, gia_tri):
        """Trường chọn thì hiện NHÃN, không hiện mã.

        Đọc thẳng ra "sunny" trên một tờ báo cáo gửi cho nhà máy là bắt
        người đọc học mã nội bộ của hệ.
        """
        f = ban_ghi._fields.get(ten_truong)
        if f and f.type == 'selection':
            return dict(f._description_selection(ban_ghi.env)).get(
                gia_tri, gia_tri or '')
        return gia_tri or ''

    def _ghi_chu_vao(self, bg, c):
        """Ghi chữ người trực gõ vào bảng nguồn, có KIỂM nếu là ô chọn.

        Gõ thẳng chuỗi tự do vào một trường chọn thì Odoo nhận rồi im
        lặng — giá trị sai nằm đó, màn hình hiện ô trống, và không ai
        biết đã mất chữ. Nên khớp theo nhãn trước, không khớp thì TỪ
        CHỐI kèm danh sách nhận được.
        """
        f = bg._fields.get(c.truong)
        gt = (self.gia_tri_chu or '').strip()
        if f is not None and f.type == 'selection':
            chon = dict(f._description_selection(bg.env))
            if gt in chon:
                return gt, None
            cho_nhan = {(v or '').strip().lower(): k
                        for k, v in chon.items()}
            if gt.lower() in cho_nhan:
                return cho_nhan[gt.lower()], None
            if not gt:
                return False, None
            return None, _('ô này chỉ nhận: %s',
                           ', '.join(chon.values()))
        return gt, None

    def _rot_kpi(self, ctx, c):
        k = ctx['kpi']
        gt, loi = self._lay_truong(k, c.truong, _('hiệu suất'))
        if loi:
            return self._chua_do(loi)
        # PR mà mẫu số chưa chốt thì KHÔNG đưa lên tờ như một con số
        # bình thường: khoảng lệch mẫu số đang treo chờ nhà máy trả lời,
        # và tờ báo cáo là chỗ cuối cùng nên giấu chuyện đó.
        if c.truong == 'pr' and getattr(k, 'lech_mau_so', 0):
            return self._chua_do(_(
                'mẫu số PR còn lệch %.2f%% so với tờ của nhà máy — chưa '
                'chốt thì chưa đưa lên báo cáo', k.lech_mau_so))
        if c.kieu == 'chu':
            return self._dat(self._ra_chu(k, c.truong, gt),
                             k.display_name, chu=True)
        self._dat(gt * c.he_so, k.display_name)

    def _rot_avail(self, ctx, c):
        a = ctx['avail']
        gt, loi = self._lay_truong(a, c.truong, _('khả dụng'))
        if loi:
            return self._chua_do(loi)
        # Khả dụng theo sản lượng có cờ riêng nói nó đo được hay không.
        if c.truong == 'kd_san_luong' and not a.do_duoc_sl:
            return self._chua_do(a.ly_do_chua_do or _('chưa đo được'))
        if c.kieu == 'chu':
            return self._dat(self._ra_chu(a, c.truong, gt),
                             a.display_name, chu=True)
        self._dat(gt * c.he_so, a.display_name)

    def _rot_chain(self, ctx, c):
        nut = self.env['eam.chain.node'].search([
            ('plant_id', '=', self.report_id.plant_id.id),
            ('code', '=', c.node_code)], limit=1)
        if not nut:
            co = ', '.join(self.env['eam.chain.node'].search([
                ('plant_id', '=', self.report_id.plant_id.id)]
            ).mapped('code'))
            return self._chua_do(_(
                'nhà máy chưa có bậc đo mã "%(m)s"; đang có: %(c)s',
                m=c.node_code, c=co or _('chưa khai bậc nào')))
        d = self.env['eam.chain.day'].search([
            ('node_id', '=', nut.id), ('date', '=', self.report_id.date)],
            limit=1)
        gt, loi = self._lay_truong(d, c.truong, _('bậc đo %s') % c.node_code)
        if loi:
            return self._chua_do(loi)
        if c.kieu == 'chu':
            return self._dat(self._ra_chu(d, c.truong, gt),
                             d.display_name, chu=True)
        self._dat(gt * c.he_so, d.display_name)

    def _rot_downtime(self, ctx, c):
        if ctx.get('dung') is None:
            ctx['dung'] = self.report_id.plant_id.gio_theo_nhom(
                ctx['tu'], ctx['den'])
        theo = ctx['dung']
        if c.group_id:
            d = theo.get(c.group_id.name)
            if d is None:
                # Không có khoảng dừng nào thuộc nhóm này trong ngày là
                # một sự thật ĐO ĐƯỢC: bằng không, không phải thiếu số.
                return self._dat(0.0, _('không có khoảng dừng nhóm này'))
            gt = d['kwh'] if c.truong == 'kwh' else d['gio']
            return self._dat(gt * c.he_so, _('%d khoảng dừng', d['so']))
        tong = sum(v['kwh' if c.truong == 'kwh' else 'gio']
                   for v in theo.values())
        self._dat(tong * c.he_so, _('%d nhóm', len(theo)))

    def _rot_historian(self, ctx, c):
        tags = self._tim_tag(c.tag_code)
        if not tags:
            return self._chua_do(_(
                'nhà máy chưa có điểm đo nào khớp mã "%s"', c.tag_code))
        kq = self.env['eam.historian'].tom_tat_ngay(
            tags.ids, ctx['tu'], ctx['den'], c.nguong, c.gop_nhieu)
        if kq is None:
            return self._chua_do(_('không tra được điểm đo'))
        if kq.get('loi'):
            return self._chua_do(kq['loi'])
        if not kq.get('n'):
            return self._chua_do(_(
                '%(n)d điểm đo khớp mã "%(m)s" nhưng không có số đo nào '
                'trong ngày', n=len(tags), m=c.tag_code))
        if c.cach_lay == 'dinh_luc':
            ts = kq.get('dinh_luc')
            if not ts:
                return self._chua_do(_('không xác định được thời điểm đỉnh'))
            # Kho chuỗi thời gian lưu theo UTC. In thẳng ra tờ báo cáo là
            # lệch bảy tiếng — mà "đỉnh gió lúc 4h sáng" nghe vẫn hợp lý
            # nên không ai nghi. Đổi về giờ TẠI NHÀ MÁY.
            mui = pytz.timezone(self.report_id._mui_gio())
            tai_cho = pytz.UTC.localize(ts).astimezone(mui)
            return self._dat(tai_cho.strftime('%H:%M'),
                             _('đỉnh %(d).1f lúc %(g)s giờ %(m)s',
                               d=kq.get('dinh') or 0,
                               g=tai_cho.strftime('%H:%M'),
                               m=mui.zone), chu=True)
        khoa = {'gop': 'gop', 'dinh': 'dinh',
                'gio_tren_nguong': 'gio_tren_nguong'}.get(
                    c.cach_lay or 'gop', 'gop')
        gt = kq.get(khoa)
        if gt is None:
            return self._chua_do(_(
                'cách gộp của điểm đo không cho ra số cho ngày này — '
                'thường là đồng hồ luỹ kế bị thay hoặc quay vòng'))
        self._dat(gt * c.he_so, _(
            '%(d)d điểm đo · %(n)d số đo · %(q)d nghi ngờ',
            d=kq.get('so_diem_do', 1), n=kq['n'], q=kq.get('n_nghi', 0)))

    def _tim_tag(self, ma):
        """Tra điểm đo theo mã, trong phạm vi NHÀ MÁY của tờ báo cáo.

        Không giới hạn theo nhà máy thì mã "T01_P" của nhà máy này khớp
        luôn điểm đo cùng tên của nhà máy khác — và tờ báo cáo lặng lẽ
        báo số của một nhà máy không liên quan.
        """
        self.ensure_one()
        T = self.env['eam.tag']
        dk = [('plant_id', '=', self.report_id.plant_id.id)]
        ma = (ma or '').strip()
        if '*' in ma:
            dk.append(('code', '=like', ma.replace('*', '%')))
        else:
            dk.append(('code', '=', ma))
        return T.search(dk, order='code')

    def _rot_nguoi(self, ctx, c):
        """Người trực tự điền — máy không đụng vào."""
        return
