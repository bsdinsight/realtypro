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

import re
from datetime import timedelta

import pytz

from odoo import _, api, fields, models
from odoo.tools.safe_eval import safe_eval

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

        Ô SỐ chỉ mơ hồ ở đúng một giá trị: SỐ KHÔNG. Nhập 0 khách và
        chưa đếm khách là hai chuyện khác nhau, và chỉ cái nút phân biệt
        được — nên ở 0 thì cờ vẫn do người gạt. Nhưng một con số KHÁC
        không thì không mơ hồ: gõ được 7 nghĩa là đã đếm. Để nguyên cờ
        tắt ở đó là bản in ra "—" cho ô vừa ghi 7 — cùng một lỗi với ô
        chữ, chỉ khác chỗ xảy ra.
        """
        if 'gia_tri_chu' in vals:
            for l in self.filtered(lambda x: x.nguon == 'nguoi'
                                   and x.kieu == 'chu'):
                co = bool((l.gia_tri_chu or '').strip())
                if l.do_duoc != co:
                    super(EamDailyReportLine, l).write({'do_duoc': co})
        if 'gia_tri' in vals and 'do_duoc' not in vals:
            for l in self.filtered(lambda x: x.nguon == 'nguoi'
                                   and x.kieu != 'chu'
                                   and x.gia_tri and not x.do_duoc):
                super(EamDailyReportLine, l).write({'do_duoc': True})

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

    def _rot_avail_hop_dong(self, c):
        """Khả dụng luỹ kế trong KỲ HỢP ĐỒNG, tới ngày của tờ.

        Kỳ khả dụng hợp đồng không trùng năm dương lịch: hợp đồng O&M
        chạy từ ngày nghiệm thu, nên "khả dụng năm nay" theo lịch và
        theo hợp đồng là hai con số khác nhau — và chỉ con số theo hợp
        đồng mới là căn cứ phạt.
        """
        ngay = self.report_id.date
        nm = self.report_id.plant_id
        hd = self.env['eam.om.contract'].search(
            [('date_start', '<=', ngay), ('date_end', '>=', ngay)])
        rieng = hd.filtered(
            lambda h: nm in h.plant_line_ids.mapped('plant_id'))
        hd = rieng[:1] or hd[:1]
        if not hd:
            return self._chua_do(_(
                'nhà máy chưa có hợp đồng O&M nào phủ ngày %s', ngay))
        ds = self.env['eam.availability.day'].search(
            [('plant_id', '=', nm.id),
             ('date', '>=', hd.date_start), ('date', '<=', ngay)])
        if not ds:
            return self._chua_do(_(
                'chưa có ngày khả dụng nào trong kỳ hợp đồng %(t)s–%(d)s',
                t=hd.date_start, d=ngay))
        # Cộng TỬ SỐ và MẪU SỐ rồi mới chia — không lấy trung bình các
        # phần trăm: ngày lặng gió mất ít điện mà khả dụng vẫn thấp, lấy
        # trung bình thì nó cùng trọng số với ngày gió mạnh.
        that = sum(ds.mapped('sl_that'))
        mat = sum(ds.mapped('sl_mat'))
        if not (that + mat):
            return self._chua_do(_('kỳ hợp đồng chưa có sản lượng nào'))
        thieu = (ngay - hd.date_start).days + 1 - len(ds)
        self._dat(100.0 * that / (that + mat) * c.he_so, _(
            '%(h)s · %(t)s→%(d)s · %(n)d ngày có số%(x)s',
            h=hd.name, t=hd.date_start, d=ngay, n=len(ds),
            x=(_(' · THIẾU %d ngày') % thieu) if thieu > 0 else ''))

    def _rot_avail(self, ctx, c):
        if c.loai_ky == 'hop_dong':
            return self._rot_avail_hop_dong(c)
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
        # Bỏ TRỐNG mã bậc nghĩa là "mọi bậc sản lượng" — dùng cho dòng
        # tổng tổn thất. Trước đây dòng ấy phải mượn nguồn giờ dừng, mà
        # giờ dừng cho ra SẢN LƯỢNG MẤT DO DỪNG MÁY: hai khái niệm khác
        # hẳn nhau, và con số mượn ấy lớn gấp mười sáu lần tổn thất thật
        # trên cùng tờ giấy.
        if not c.node_code:
            return self._rot_chain_tong(c)
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
        if c.loai_ky and c.loai_ky != 'ngay':
            return self._rot_chain_luy_ke(c, nut)
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

    def _rot_chain_tong(self, c):
        """Cộng một trường trên MỌI bậc sản lượng — dòng tổng của chuỗi.

        Chỉ cộng bậc loại SẢN LƯỢNG. Điện tự dùng và tiêu thụ ban đêm
        là tiêu thụ CÓ CHỦ ĐÍCH, không phải tổn thất; gộp chúng vào tổng
        tổn thất là đổ cho đường dây một khoản mà đường dây không gây ra.
        """
        N = self.env['eam.chain.node']
        D = self.env['eam.chain.day']
        nut = N.search([('plant_id', '=', self.report_id.plant_id.id),
                        ('node_type', '=', 'san_luong')])
        if not nut:
            return self._chua_do(_('nhà máy chưa khai bậc sản lượng nào'))
        if c.loai_ky and c.loai_ky != 'ngay':
            tu, den = self._bien_ky(c.loai_ky)
        else:
            tu = den = self.report_id.date
        ds = D.search([('node_id', 'in', nut.ids),
                       ('date', '>=', tu), ('date', '<=', den)])
        if not ds:
            return self._chua_do(_(
                'chuỗi đo chưa có dòng ngày nào trong %(t)s–%(d)s',
                t=tu, d=den))
        if c.truong not in ds._fields:
            return self._chua_do(_(
                'bảng bậc đo không có trường "%s"', c.truong))
        self._dat(sum(ds.mapped(c.truong)) * c.he_so, _(
            '%(b)d bậc sản lượng · %(n)d dòng ngày · %(t)s–%(d)s',
            b=len(nut), n=len(ds), t=tu, d=den))

    def _bien_ky(self, loai):
        """Biên của kỳ, tính TỚI NGÀY CỦA TỜ chứ không tới hết kỳ.

        Tờ báo cáo ngày 17/10 nói "luỹ kế tháng", nghĩa là 01→17/10 —
        không phải cả tháng 10. Lấy cả kỳ thì con số luôn to hơn, và to
        hơn theo một cách trông vẫn hợp lý.
        """
        ngay = self.report_id.date
        if loai == 'tuan':
            return ngay - timedelta(days=ngay.weekday()), ngay
        if loai == 'thang':
            return ngay.replace(day=1), ngay
        if loai == 'nam':
            return ngay.replace(month=1, day=1), ngay
        return ngay, ngay

    def _rot_chain_luy_ke(self, c, nut):
        """Cộng một trường của bậc đo trên cả kỳ, tới ngày của tờ."""
        tu, den = self._bien_ky(c.loai_ky)
        ds = self.env['eam.chain.day'].search([
            ('node_id', '=', nut.id),
            ('date', '>=', tu), ('date', '<=', den)])
        if not ds:
            return self._chua_do(_(
                'bậc đo "%(m)s" chưa có dòng ngày nào trong kỳ %(t)s–%(d)s',
                m=c.node_code, t=tu, d=den))
        if c.truong not in ds._fields:
            return self._chua_do(_(
                'bảng bậc đo không có trường "%s"', c.truong))
        thieu = (den - tu).days + 1 - len(ds)
        self._dat(sum(ds.mapped(c.truong)) * c.he_so, _(
            '%(n)d ngày có số, %(t)s–%(d)s%(x)s', n=len(ds), t=tu, d=den,
            x=(_(' · THIẾU %d ngày') % thieu) if thieu > 0 else ''))

    def _rot_ky(self, ctx, c):
        """Sản lượng / doanh thu của một KỲ, đọc bảng kỳ đã dựng sẵn.

        Không cộng lại ở đây: bảng kỳ đã là nơi quyết định "kỳ này nhà
        máy phát bao nhiêu", kèm số ngày CÓ số và số ngày thiếu. Cộng
        lần hai là mở đường cho hai con số cho cùng một tháng.
        """
        P = self.env['eam.energy.period']
        loai = c.loai_ky or 'ngay'
        tu, _den = self._bien_ky(loai)
        r = P.search([('plant_id', '=', self.report_id.plant_id.id),
                      ('loai_ky', '=', loai), ('tu_ngay', '=', tu)], limit=1)
        if not r:
            return self._chua_do(_(
                'chưa dựng dòng kỳ %(l)s bắt đầu %(t)s cho nhà máy này — '
                'mở Hiệu suất → Sản lượng theo kỳ và dựng', l=loai, t=tu))
        gt, loi = self._lay_truong(r, c.truong, _('sản lượng theo kỳ'))
        if loi:
            return self._chua_do(loi)
        # TỶ LỆ trên kỳ thiếu ngày thì SAI, không phải "nhỏ hơn thật".
        # Tổng thiếu ngày vẫn là một phần của tổng — ai đọc cũng hiểu
        # 12,3 triệu kWh là chưa đủ năm. Nhưng hệ số công suất 2,92%
        # tính trên 32/365 ngày KHÔNG phải hệ số công suất thấp: mẫu số
        # là cả năm còn tử số mới có một tháng. Con số ấy nằm cạnh "PR
        # cam kết" và "khả dụng" thì người đọc sẽ so nó với cam kết.
        #
        # Đơn vị là thứ dòng hồ sơ ĐÃ KHAI, nên dùng nó làm dấu hiệu —
        # không đoán theo tên trường.
        if (c.don_vi or '').strip() == '%' and r.so_ngay and \
                r.so_ngay_co_so < r.so_ngay * 0.5:
            return self._chua_do(_(
                'kỳ %(k)s mới có %(a)d/%(b)d ngày có số — một TỶ LỆ tính '
                'trên nửa kỳ còn thiếu thì sai chứ không phải nhỏ hơn '
                'thật, vì mẫu số là cả kỳ', k=r.nhan_ky or '',
                a=r.so_ngay_co_so, b=r.so_ngay))
        vet = r.nhan_ky or ''
        if r.so_ngay_thieu:
            # Kỳ thiếu ngày vẫn ra một con số dương trông bình thường,
            # chỉ nhỏ hơn thật. Đặt số ngày thiếu ngay cạnh.
            vet = _('%(k)s · THIẾU %(n)d/%(t)d ngày', k=vet,
                    n=r.so_ngay_thieu, t=r.so_ngay)
        self._dat(gt * c.he_so, vet)

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
            cac = [d]
        else:
            cac = list(theo.values())
        if not cac:
            return self._dat(0.0, _('không có khoảng dừng nào trong ngày'))
        chua = sum(x.get('chua_tien', 0) for x in cac)
        if c.truong == 'tien' and chua:
            # Giá điện chưa khai thì tổng tiền nhỏ hơn thật mà vẫn là
            # một con số dương — "53.560 kWh mất = 48 đồng" trông như đã
            # tính xong, và không ai bấm máy tính lại một dòng báo cáo.
            return self._chua_do(_(
                '%(n)d khoảng dừng đã có sản lượng mất nhưng CHƯA quy ra '
                'tiền — khai giá điện trên nhà máy hoặc hợp đồng mua bán '
                'điện, rồi bấm tính tiền trên sổ dừng máy', n=chua))
        khoa = {'kwh': 'kwh', 'tien': 'tien'}.get(
            c.truong, 'gio' if c.truong != 'gio_nm' else 'gio')
        tong = sum(x[khoa] for x in cac)
        vet = _('%(n)d khoảng dừng · %(g)d nhóm',
                n=sum(x['so'] for x in cac), g=len(cac))
        if c.truong == 'gio_nm':
            # GIỜ-MÁY khác GIỜ-NHÀ MÁY, và đó là chỗ một tờ báo cáo nói
            # sai mà không ai bắt được. Bốn bộ nghịch lưu dừng một tiếng
            # là 4 giờ-máy, nhưng nhà máy vẫn chạy suốt — trừ 4 giờ ấy
            # khỏi giờ vận hành của NHÀ MÁY là trộn hai mẫu số, và ra
            # một con số nhỏ hơn thật mà vẫn dương nên trông vẫn hợp lý.
            n = self.report_id._so_to_may()
            if not n:
                return self._chua_do(_(
                    'nhà máy chưa khai số tổ máy, nên không quy được '
                    'giờ-máy về giờ cấp nhà máy'))
            tong = tong / float(n)
            vet = _('%(v)s · quy về cấp nhà máy: chia cho %(n)d tổ máy',
                    v=vet, n=n)
        self._dat(tong * c.he_so, vet)

    def _rot_gio_vh(self, ctx, c):
        """Ba con số giờ vận hành trong ngày, tính ở MỘT chỗ.

        Tờ báo cáo của nhà máy in cả ba: giờ vận hành danh nghĩa, tổng
        giờ dừng, và giờ vận hành dùng cho tỷ số hiệu suất. Con số thứ
        ba là hiệu của hai con số đầu — để nó tự tính ở chỗ khác là mở
        đường cho ba dòng trên cùng một tờ không trừ ra nhau.

        ``danh_nghia``  khoảng từ lúc nhà máy bắt đầu phát tới lúc ngắt
                        cuối cùng. KHÔNG phải số giờ có số đo: nhà máy
                        gửi số suốt đêm với giá trị 0.
        ``dung``        tổng giờ dừng mọi nhóm trong ngày.
        ``cho_pr``      danh nghĩa trừ giờ dừng.
        """
        tags = self.report_id._tag_cong_suat()
        if not tags:
            return self._chua_do(_(
                'nhà máy chưa khai điểm đo nào loại "công suất"'))
        kq = self.env['eam.historian'].tom_tat_ngay(
            tags.ids, ctx['tu'], ctx['den'], c.nguong, True)
        if not kq or kq.get('loi') or not kq.get('n'):
            return self._chua_do((kq or {}).get('loi') or _(
                'không có số đo công suất nào trong ngày'))
        dau, cuoi = kq.get('moc_dau'), kq.get('moc_cuoi')
        if not dau or not cuoi:
            return self._chua_do(_(
                'không mốc đo nào vượt ngưỡng %.1f trong ngày',
                c.nguong or 0))
        danh_nghia = (cuoi - dau).total_seconds() / 3600.0
        mui = pytz.timezone(self.report_id._mui_gio())
        khung = _('%(a)s → %(b)s giờ %(m)s',
                  a=pytz.UTC.localize(dau).astimezone(mui).strftime('%H:%M'),
                  b=pytz.UTC.localize(cuoi).astimezone(mui).strftime('%H:%M'),
                  m=mui.zone)
        if c.truong == 'danh_nghia':
            return self._dat(danh_nghia * c.he_so, khung)
        if ctx.get('dung') is None:
            ctx['dung'] = self.report_id.plant_id.gio_theo_nhom(
                ctx['tu'], ctx['den'])
        # Giờ dừng cộng ra GIỜ-MÁY; khung phát ở trên là GIỜ-NHÀ MÁY.
        # Phải quy về cùng một mẫu số trước khi trừ.
        n_may = self.report_id._so_to_may()
        if not n_may:
            return self._chua_do(_(
                'nhà máy chưa khai số tổ máy, nên không quy được giờ-máy '
                'về giờ cấp nhà máy'))
        tong_dung = sum(x['gio'] for x in ctx['dung'].values()) / float(n_may)
        if c.truong == 'dung':
            return self._dat(tong_dung * c.he_so, _(
                '%(g)d nhóm có giờ dừng · quy về cấp nhà máy: chia cho '
                '%(n)d tổ máy',
                g=len([x for x in ctx['dung'].values() if x['gio']]),
                n=n_may))
        # Khoảng dừng NẰM NGOÀI khung phát — ban đêm chẳng hạn — vẫn vào
        # tổng giờ dừng, nên hiệu có thể âm. Kẹp về 0 và nói ra, thay vì
        # in một số giờ âm trông như lỗi gõ phím.
        con = danh_nghia - tong_dung
        if con < 0:
            return self._dat(0.0, _(
                'giờ dừng (%(d).2f h) vượt khung phát (%(k).2f h) — có '
                'khoảng dừng nằm ngoài giờ phát', d=tong_dung, k=danh_nghia))
        self._dat(con * c.he_so, _(
            '%(k).2f h khung phát trừ %(d).2f h giờ dừng · %(w)s',
            k=danh_nghia, d=tong_dung, w=khung))

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
        # Ba cách lấy cho ra một MỐC THỜI GIAN chứ không phải một con số.
        if c.cach_lay in ('dinh_luc', 'moc_dau', 'moc_cuoi'):
            ts = kq.get(c.cach_lay)
            if not ts:
                return self._chua_do(
                    _('không xác định được thời điểm đỉnh')
                    if c.cach_lay == 'dinh_luc' else
                    _('không có số đo nào vượt ngưỡng trong ngày'))
            # Kho chuỗi thời gian lưu theo UTC. In thẳng ra tờ báo cáo là
            # lệch bảy tiếng — mà "đỉnh gió lúc 4h sáng" nghe vẫn hợp lý
            # nên không ai nghi. Đổi về giờ TẠI NHÀ MÁY.
            mui = pytz.timezone(self.report_id._mui_gio())
            tai_cho = pytz.UTC.localize(ts).astimezone(mui)
            g = tai_cho.strftime('%H:%M')
            if c.cach_lay == 'dinh_luc':
                vet = _('đỉnh %(d).1f lúc %(g)s giờ %(m)s',
                        d=kq.get('dinh') or 0, g=g, m=mui.zone)
            else:
                vet = _('%(l)s vượt %(n).1f lúc %(g)s giờ %(m)s',
                        l=(_('lần đầu') if c.cach_lay == 'moc_dau'
                           else _('lần cuối')),
                        n=c.nguong or 0, g=g, m=mui.zone)
            return self._dat(g, vet, chu=True)
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

    def _rot_unit(self, ctx, c):
        """Lấy một ô của dòng TỔNG trong bảng tổ máy.

        Không cộng lại từ đầu: gọi đúng hàm đã dựng dòng TỔNG của bảng,
        để tờ báo cáo và bảng tổ máy không bao giờ ra hai con số cho
        cùng một ngày.
        """
        t = self.env['eam.unit.day'].tong_ngay(
            self.report_id.plant_id, self.report_id.date)
        if not t:
            return self._chua_do(_(
                'chưa dựng bảng tổ máy cho ngày này — mở "Hiệu suất tổ '
                'máy" và dựng, hoặc chờ cron chạy lúc 0h10'))
        if c.truong not in t:
            return self._chua_do(_(
                'dòng TỔNG của bảng tổ máy không có ô "%(t)s"; đang có: '
                '%(c)s', t=c.truong, c=', '.join(sorted(t))))
        gt = t[c.truong]
        if gt is None:
            return self._chua_do(_(
                'ô "%s" của dòng TỔNG chưa tính được — xem lý do trên '
                'chính bảng tổ máy', c.truong))
        self._dat(gt * c.he_so, _('dòng TỔNG của %d tổ máy',
                                  t.get('so_to_may', 0)))

    def _rot_target(self, ctx, c):
        """Mục tiêu sản lượng: luỹ kế tới ngày này, hoặc CẢ THÁNG."""
        T = self.env['eam.energy.target']
        ngay = self.report_id.date
        # Mục tiêu CẢ THÁNG đọc thẳng bản ghi tháng, không đi qua phép
        # luỹ kế. Mục tiêu khai "không rải theo ngày" thì phép luỹ kế từ
        # chối trả số trước ngày cuối tháng — đúng với dòng luỹ kế, sai
        # với dòng cả tháng: con số ấy có sẵn từ đầu tháng.
        if c.truong == 'ca_thang':
            t = T.cua_thang(self.report_id.plant_id, ngay)
            if not t:
                return self._chua_do(_(
                    'chưa khai mục tiêu cho tháng %(t)02d/%(n)d của nhà '
                    'máy này', t=ngay.month, n=ngay.year))
            return self._dat(t[c.muc] * c.he_so, _(
                'mục tiêu CẢ THÁNG %(t)02d/%(n)d · nguồn: %(g)s',
                t=ngay.month, n=ngay.year, g=t.nguon))
        lk = T.luy_ke_den(self.report_id.plant_id, ngay)
        if not lk.get('do_duoc'):
            return self._chua_do(lk.get('ly_do') or _('chưa khai mục tiêu'))
        # Nói rõ con số là CHIA ĐỀU. Trình bày nó như mục tiêu riêng của
        # ngày hôm nay là để người đọc tin vào một độ chính xác không có.
        vet = (_('mục tiêu tháng chia đều %(a)d/%(b)d ngày · nguồn: %(n)s',
                 a=lk['ngay_thu'], b=lk['so_ngay_thang'], n=lk['nguon'])
               if lk['cach_rai'] == 'deu'
               else _('mục tiêu cả tháng · nguồn: %s', lk['nguon']))
        self._dat(lk[c.muc] * c.he_so, vet)

    def _rot_nha_may(self, ctx, c):
        """Hằng số khai trên hồ sơ nhà máy — diện tích pin, hệ số nhiệt…

        Mấy con số này KHÔNG đổi theo ngày, nhưng vẫn phải in lên tờ:
        mẫu số tỷ số hiệu suất dựng trên chúng, và ba tháng sau khi PR
        bị chất vấn thì tờ giấy phải tự nói được nó tính bằng diện tích
        nào.
        """
        nm = self.report_id.plant_id
        gt, loi = self._lay_truong(nm, c.truong, _('hồ sơ nhà máy'))
        if loi:
            return self._chua_do(loi)
        if not gt:
            # Hằng số bằng 0 là CHƯA KHAI, không phải "bằng không":
            # diện tích tấm pin không thể bằng 0 trên một nhà máy đang
            # phát điện.
            return self._chua_do(_(
                'hằng số "%(t)s" chưa khai trên hồ sơ nhà máy %(n)s',
                t=c.truong, n=nm.display_name))
        if c.kieu == 'chu':
            return self._dat(self._ra_chu(nm, c.truong, gt),
                             nm.display_name, chu=True)
        self._dat(gt * c.he_so, _('hồ sơ nhà máy %s', nm.display_name))

    def _rot_cong_thuc(self, ctx, c):
        """Tính từ các dòng KHÁC trên cùng tờ, trỏ bằng mã dòng.

        Có hai dòng trên tờ của nhà máy không đọc được từ bảng nào —
        chúng là phép tính giữa những dòng khác: tỷ lệ điện tự dùng, và
        sản lượng gộp tại điểm giao nhận. Viết chúng vào mã là chôn một
        công thức của MỘT nhà máy vào sản phẩm dùng chung.

        Luật quan trọng nhất ở đây là TỪ CHỐI: đầu vào chưa đo được thì
        kết quả cũng chưa đo được, kèm tên mã còn thiếu. Thay số thiếu
        bằng 0 cho ra một tỷ lệ trông vẫn hợp lý — và sai.
        """
        bieu = (c.cong_thuc or '').strip()
        if not bieu:
            return self._chua_do(_(
                'dòng khai nguồn "công thức" nhưng chưa viết công thức'))
        so, thieu_so = {}, {}
        for l in self.report_id.line_ids:
            ma = l.profile_line_id.ma
            if not ma or (l.kieu or '') == 'chu':
                continue
            if l.do_duoc:
                so[ma] = l.gia_tri
            else:
                thieu_so[ma] = l.ly_do_chua_do or _('chưa đo được')
        can = set(re.findall(r'[A-Za-z_][A-Za-z0-9_]*', bieu))
        thieu = sorted(t for t in can if t not in so)
        if thieu:
            return self._chua_do(_(
                'công thức cần %(c)s nhưng %(t)s chưa có số%(v)s',
                c=', '.join(sorted(can)), t=', '.join(thieu),
                v=(' (%s)' % thieu_so[thieu[0]]) if thieu[0] in thieu_so
                else _(' — chưa dòng nào trên tờ mang mã đó')))
        try:
            gt = safe_eval(bieu, dict(so))
        except ZeroDivisionError:
            return self._chua_do(_(
                'mẫu số bằng không trong công thức "%s"', bieu))
        except Exception as e:                        # noqa: BLE001
            return self._chua_do(_('công thức hỏng: %s', str(e)[:80]))
        self._dat(gt * c.he_so, _('= %(b)s, với %(v)s', b=bieu, v=' · '.join(
            '%s=%s' % (k, round(v, 3)) for k, v in sorted(so.items())
            if k in can)))

    def _rot_cong_to(self, ctx, c):
        """Chênh hai lần đọc của MỘT công-tơ — cùng luật với khối bảng.

        Thiếu một trong hai lần đọc thì TỪ CHỐI. Lấy số đọc gần nhất
        thay cho số đọc hôm qua là âm thầm cộng sản lượng nhiều ngày vào
        một ngày — con số vẫn dương, vẫn hợp lý, và chỉ lộ khi cộng cả
        tháng lại thấy vượt.
        """
        from datetime import timedelta
        vt = self.env['eam.location'].search(
            [('code', '=', c.ma_cong_to),
             ('id', 'child_of', self.report_id.plant_id.id)], limit=1)
        if not vt:
            return self._chua_do(_(
                'nhà máy chưa có vị trí đo mã "%s"', c.ma_cong_to))
        m = self.env['eam.meter'].search(
            [('location_id', '=', vt.id)], limit=1)
        if not m:
            return self._chua_do(_(
                'vị trí "%s" chưa gắn công-tơ nào', vt.display_name))
        R = self.env['eam.meter.reading']
        hq = R.search([('meter_id', '=', m.id),
                       ('date', '=', self.report_id.date - timedelta(days=1))],
                      limit=1)
        hn = R.search([('meter_id', '=', m.id),
                       ('date', '=', self.report_id.date)], limit=1)
        if not hn:
            return self._chua_do(_('công-tơ "%s" chưa có số đọc hôm nay',
                                   vt.name or vt.code))
        if not hq:
            return self._chua_do(_(
                'công-tơ "%s" chưa có số đọc hôm qua — không tính chênh '
                'được', vt.name or vt.code))
        if hn.is_reset:
            return self._chua_do(_(
                'công-tơ "%s" đã được thay hoặc quay vòng trong ngày',
                vt.name or vt.code))
        ra = (hn.effective_value or 0.0) - (hq.effective_value or 0.0)
        if ra < 0:
            return self._chua_do(_(
                'số đọc hôm nay (%(b)s) NHỎ HƠN hôm qua (%(a)s)',
                b=hn.effective_value, a=hq.effective_value))
        self._dat(ra * c.he_so, _(
            '%(v)s · %(a)s → %(b)s', v=vt.name or vt.code,
            a=hq.effective_value, b=hn.effective_value))

    def _rot_khoi(self, ctx, c):
        """Khối dựng sẵn — bản in tự chèn, dòng này chỉ đánh dấu chỗ."""
        nhan = dict(c._fields['khoi_dac_biet'].selection).get(
            c.khoi_dac_biet, '')
        self.write({'do_duoc': True,
                    'gia_tri_chu': _('(khối: %s)', nhan),
                    'ly_do_chua_do': False,
                    'nguon_ghi': _('khối dựng sẵn: %s',
                                   dict(c._fields['khoi_dac_biet'].selection
                                        ).get(c.khoi_dac_biet, ''))})

    def _rot_nguoi(self, ctx, c):
        """Người trực tự điền — máy không đụng vào."""
        return
