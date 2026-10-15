# -*- coding: utf-8 -*-
"""Mùa, và luật ưu tiên công việc theo mùa.

Mùa là một CỬA SỔ LẶP HẰNG NĂM, không phải một khoảng ngày
----------------------------------------------------------
Mùa mưa Savannakhet là *tháng 5 tới tháng 10*, năm nào cũng vậy. Khai
bằng hai ngày đầy đủ (01/05/2026 → 31/10/2026) thì sang 2027 phải khai
lại, và ai quên khai thì mọi luật mùa im lặng ngừng áp dụng — không báo
gì. Nên ở đây chỉ lưu **ngày-tháng**, và cửa sổ tự lặp.

Kéo theo: mùa **vắt qua năm mới** phải chạy được. Mùa gió mạnh tháng 11
tới tháng 3 là một mùa, không phải hai.

Vì sao "làm SỚM" chứ không phải "làm MUỘN"
------------------------------------------
Đây là chỗ các hệ lập lịch theo mùa làm sai, và sai theo hướng nguy
hiểm. Hạn thay dầu hộp số rơi vào giữa mùa mưa, không leo trụ được. Lối
xử lý tự nhiên của phần mềm là **đẩy sang sau mùa mưa** — và thế là hộp
số chạy thêm bốn tháng quá kỳ thay dầu, **xuyên qua đúng mùa khắc nghiệt
nhất**.

Đúng phải là **kéo lên trước khi mùa bắt đầu**. Với bảo trì phòng ngừa,
làm sớm là an toàn, làm muộn là rủi ro — hai hướng không đối xứng. Nên
thuật toán ở đây tìm ngày lùi về trước hết rồi mới tìm ngày tiến lên,
và khi hai bên bằng điểm thì chọn bên sớm.

Kiểm định bắt buộc thì KHÔNG dời
---------------------------------
Hạn kiểm định do pháp luật đặt. Dời nó để tránh mùa mưa là đẩy thiết bị
sang trạng thái hết hiệu lực kiểm định — quá hạn là phải dừng thiết bị,
không phải chỉ số xấu đi. Nên công việc loại *kiểm định bắt buộc* được
**báo xung đột mùa nhưng không bao giờ bị dời**: việc phải làm là chuẩn
bị khác (thuê cẩu chịu gió, dựng che chắn), không phải hoãn.

Hạn gốc KHÔNG bị ghi đè
-----------------------
Ngày đề xuất theo mùa là một cột **riêng**. Ghi đè lên hạn thật thì mất
luôn thông tin "việc này lẽ ra tới hạn ngày nào", và sau vài lần dời
không ai biết thiết bị đã trễ bao lâu so với chu kỳ thiết kế.
"""
import calendar
from datetime import date, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

LOAI_MUA = [
    ('rain', 'Mùa mưa'),
    ('dry', 'Mùa khô'),
    ('high_wind', 'Mùa gió mạnh'),
    ('low_wind', 'Mùa lặng gió'),
    ('typhoon', 'Mùa bão'),
    ('high_output', 'Mùa phát cao'),
    ('other', 'Khác'),
]

CHINH_SACH = [
    ('prefer', 'Nên làm trong mùa này'),
    ('avoid', 'Nên tránh'),
    ('forbid', 'Không làm được'),
]
# Chỉ "tránh" và "không làm được" mới ĐƯỢC PHÉP làm dời ngày.
#
# "Nên làm" cố ý KHÔNG có quyền đó, và đây là một quyết định chứ không
# phải thiếu sót: nếu để nó dời được thì hệ thống sẽ sẵn sàng đẩy việc
# lùi ba tuần để rơi vào mùa khô — tức đúng cái hướng nguy hiểm mà cả
# module này được viết ra để tránh. "Nên làm" chỉ dùng để CHỌN giữa
# những ngày đã bằng điểm, và để ghi chú.
DIEM_CUNG = {'avoid': 1, 'forbid': 2}


def _ngay_an_toan(nam, thang, ngay):
    """Dựng ngày mà không nổ vì tháng ngắn.

    Mùa khai "đến 31" rơi vào tháng 30 ngày, hoặc 29/02 ở năm không
    nhuận, sẽ làm ``date()`` ném lỗi — và vì nó nằm trong hàm tính của
    một trường lưu, cả danh sách lịch bảo trì trắng màn hình. Kẹp về
    ngày cuối tháng.
    """
    cuoi = calendar.monthrange(nam, thang)[1]
    return date(nam, thang, min(ngay, cuoi))


class EamSeason(models.Model):
    _name = 'eam.season'
    _description = 'Mùa trong năm'
    _order = 'month_from, day_from'

    name = fields.Char(string='Tên mùa', required=True)
    season_kind = fields.Selection(
        LOAI_MUA, string='Loại mùa', required=True, default='rain')
    plant_id = fields.Many2one(
        'eam.location', string='Nhà máy',
        domain="[('location_type', '=', 'plant')]", index=True,
        help='Để trống thì áp cho mọi nhà máy. Mùa là chuyện địa phương — '
             'mùa mưa Savannakhet không trùng mùa mưa Đắk Lắk, nên gần như '
             'luôn phải khai theo nhà máy.')
    # Nhãn phải KHÁC nhau. Hai trường cùng nhãn "ngày" làm Odoo kêu lúc
    # nạp, và tệ hơn là lúc xuất Excel hai cột trông y hệt nhau.
    month_from = fields.Integer(string='Từ tháng', required=True, default=5)
    day_from = fields.Integer(string='Từ ngày', required=True, default=1)
    month_to = fields.Integer(string='Đến tháng', required=True, default=10)
    day_to = fields.Integer(string='Đến ngày', required=True, default=31)
    active = fields.Boolean(default=True)
    note = fields.Text(
        string='Diễn giải',
        help='Ghi điều kiện thật: gió trung bình bao nhiêu, đường vào có '
             'đi được không, cẩu có dựng được không.')
    rule_ids = fields.One2many(
        'eam.season.rule', 'season_id', string='Luật trong mùa')
    rule_count = fields.Integer(string='Số luật', compute='_compute_rule')
    window_label = fields.Char(string='Cửa sổ', compute='_compute_label',
                               store=True)
    company_id = fields.Many2one(
        'res.company', string='Công ty', required=True,
        default=lambda self: self.env.company, index=True)

    @api.depends('rule_ids')
    def _compute_rule(self):
        for s in self:
            s.rule_count = len(s.rule_ids)

    @api.depends('month_from', 'day_from', 'month_to', 'day_to')
    def _compute_label(self):
        for s in self:
            s.window_label = '%02d/%02d → %02d/%02d' % (
                s.day_from or 0, s.month_from or 0,
                s.day_to or 0, s.month_to or 0)

    @api.depends('name', 'window_label', 'plant_id')
    def _compute_display_name(self):
        for s in self:
            ten = '%s (%s)' % (s.name or '', s.window_label or '')
            if s.plant_id:
                ten = '%s · %s' % (s.plant_id.code or '', ten)
            s.display_name = ten

    @api.constrains('month_from', 'day_from', 'month_to', 'day_to')
    def _check_cua_so(self):
        for s in self:
            for th, ng in ((s.month_from, s.day_from),
                           (s.month_to, s.day_to)):
                if not 1 <= th <= 12:
                    raise ValidationError(_(
                        'Mùa "%s": tháng phải trong khoảng 1–12.', s.name))
                if not 1 <= ng <= 31:
                    raise ValidationError(_(
                        'Mùa "%s": ngày phải trong khoảng 1–31.', s.name))

    # ------------------------------------------------------------------
    def _trong_mua(self, d):
        """Ngày ``d`` có nằm trong mùa này không. Lặp hằng năm."""
        self.ensure_one()
        a = (self.month_from, self.day_from)
        b = (self.month_to, self.day_to)
        x = (d.month, d.day)
        if a <= b:
            return a <= x <= b
        # Vắt qua năm mới: tháng 11 → tháng 3 là MỘT mùa.
        return x >= a or x <= b

    def _bien_dot(self, d):
        """Ngày đầu và ngày cuối của đợt mùa đang chứa ``d``."""
        self.ensure_one()
        nam = d.year
        a = (self.month_from, self.day_from)
        b = (self.month_to, self.day_to)
        if a <= b:
            return (_ngay_an_toan(nam, *a), _ngay_an_toan(nam, *b))
        if (d.month, d.day) >= a:
            return (_ngay_an_toan(nam, *a), _ngay_an_toan(nam + 1, *b))
        return (_ngay_an_toan(nam - 1, *a), _ngay_an_toan(nam, *b))


class EamSeasonRule(models.Model):
    """Trong mùa này thì loại việc nào nên làm, nên tránh, hay không làm được."""
    _name = 'eam.season.rule'
    _description = 'Luật ưu tiên theo mùa'
    _order = 'season_id, sequence, id'

    season_id = fields.Many2one(
        'eam.season', string='Mùa', required=True, ondelete='cascade',
        index=True)
    sequence = fields.Integer(default=10)
    policy = fields.Selection(
        CHINH_SACH, string='Chính sách', required=True, default='avoid')
    work_type = fields.Selection(
        [('preventive', 'Bảo trì phòng ngừa'),
         ('predictive', 'Bảo trì theo trạng thái'),
         ('inspection', 'Kiểm tra, xem xét'),
         ('statutory', 'Kiểm định bắt buộc')],
        string='Chỉ áp cho loại việc',
        help='Để trống thì áp cho mọi loại. Lưu ý KIỂM ĐỊNH BẮT BUỘC luôn '
             'được báo xung đột nhưng KHÔNG bao giờ bị dời — hạn do pháp '
             'luật đặt.')
    trade = fields.Selection(
        [('mechanical', 'Cơ khí'), ('electrical', 'Điện'),
         ('control', 'Điều khiển, tự động'), ('blade', 'Cánh quạt'),
         ('hv', 'Điện cao áp'), ('rope', 'Tiếp cận bằng dây'),
         ('other', 'Khác')],
        string='Chỉ áp cho nghề',
        help='Để trống thì áp cho mọi nghề. Đây là chỗ luật mùa đáng tiền '
             'nhất: mùa mưa thì "tiếp cận bằng dây" không làm được, nhưng '
             'việc trong tháp vẫn làm bình thường.')
    reason = fields.Char(
        string='Lý do',
        help='Bắt buộc khi chính sách là "không làm được". Một chữ "cấm" '
             'không kèm lý do thì người ở hiện trường sẽ lách, vì họ không '
             'biết đang lách cái gì.')
    max_shift_days = fields.Integer(
        string='Cho phép dời tối đa (ngày)', default=30,
        help='Giới hạn dời để tránh mùa. Vượt giới hạn thì hệ thống BÁO là '
             'không tránh được chứ không dời tiếp — dời ba tháng để tránh '
             'mưa là đã phá chu kỳ bảo trì.')
    company_id = fields.Many2one(
        related='season_id.company_id', store=True, index=True)

    @api.constrains('policy', 'reason')
    def _check_ly_do(self):
        for r in self:
            if r.policy == 'forbid' and not r.reason:
                raise ValidationError(_(
                    'Luật "không làm được" trong mùa "%s" phải ghi lý do. '
                    'Một chữ "cấm" không kèm lý do thì người ở hiện trường '
                    'sẽ lách, vì họ không biết đang lách cái gì.',
                    r.season_id.name or ''))

    @api.depends('season_id', 'policy', 'work_type', 'trade')
    def _compute_display_name(self):
        cs = dict(CHINH_SACH)
        for r in self:
            pham_vi = []
            if r.work_type:
                pham_vi.append(dict(
                    self._fields['work_type'].selection)[r.work_type])
            if r.trade:
                pham_vi.append(dict(
                    self._fields['trade'].selection)[r.trade])
            r.display_name = '%s: %s%s' % (
                r.season_id.name or '', cs.get(r.policy, ''),
                ' — ' + ', '.join(pham_vi) if pham_vi else '')

    # ------------------------------------------------------------------
    @api.model
    def _luat_cho_ke_hoach(self, plan, location):
        """Mọi luật mùa có thể áp cho cặp (kế hoạch, vị trí) — chưa xét ngày."""
        nha_may = location.plant_id
        ds = self.search([])
        giu = self.browse()
        for r in ds:
            s = r.season_id
            if not s.active:
                continue
            if s.plant_id and nha_may and s.plant_id.id != nha_may.id:
                continue
            if r.work_type and r.work_type != plan.work_type:
                continue
            if r.trade and r.trade != plan.trade:
                continue
            giu |= r
        return giu

    @api.model
    def _diem_ngay(self, luat, d):
        """Điểm "cứng" của một ngày và các luật khớp.

        Điểm chỉ tính ``tránh`` và ``không làm được``. ``nên làm`` trả về
        riêng ở ``co_nen_lam`` để dùng làm tiêu chí phá hoà, chứ không
        được cộng vào điểm — xem chú thích ở ``DIEM_CUNG``.
        """
        khop = luat.filtered(lambda r: r.season_id._trong_mua(d))
        diem = max([DIEM_CUNG.get(r.policy, 0) for r in khop] or [0])
        co_nen_lam = any(r.policy == 'prefer' for r in khop)
        return diem, khop, co_nen_lam

    @api.model
    def _de_xuat_ngay(self, plan, location, d, hom_nay=None):
        """Ngày nên làm, xét mùa.

        Trả về ``(ngày, số ngày dời, lời giải thích, có tránh được không)``.
        Dời **âm là kéo lên sớm**, và đó là hướng được ưu tiên.
        """
        luat = self._luat_cho_ke_hoach(plan, location)
        if not luat:
            return d, 0, False, True
        hom_nay = hom_nay or fields.Date.context_today(self)
        diem_goc, khop_goc, nen_lam_goc = self._diem_ngay(luat, d)

        def ten_mua(rs, chi_xau=True):
            return ', '.join(sorted(set(
                '%s (%s)' % (r.season_id.name,
                             dict(CHINH_SACH)[r.policy]
                             + (': ' + r.reason if r.reason else ''))
                for r in rs
                if not chi_xau or r.policy in DIEM_CUNG)))

        # Kiểm định bắt buộc: BÁO xung đột, KHÔNG dời.
        if plan.work_type == 'statutory':
            if diem_goc:
                return d, 0, _(
                    'Hạn kiểm định rơi vào %(m)s. KHÔNG dời được — hạn do '
                    'pháp luật đặt, quá hạn là phải dừng thiết bị. Việc '
                    'phải làm là chuẩn bị khác, không phải hoãn.',
                    m=ten_mua(khop_goc)), False
            return d, 0, False, True

        if not diem_goc:
            return d, 0, (
                _('Hạn đang nằm trong %s — đúng mùa nên làm.',
                  ten_mua(khop_goc, chi_xau=False))
                if nen_lam_goc else False), True

        cap = max(luat.mapped('max_shift_days') or [0])
        if cap <= 0:
            return d, 0, _(
                'Hạn rơi vào %(m)s nhưng luật không cho dời ngày nào.',
                m=ten_mua(khop_goc)), False

        # Dời ÍT NHẤT có thể, và trong các ngày dời bằng nhau thì ưu tiên
        # ngày SỚM. Hai hướng không đối xứng: làm sớm là an toàn, làm
        # muộn là để thiết bị chạy quá chu kỳ thiết kế.
        for k in range(1, cap + 1):
            ung_vien = []
            for huong in (-1, 1):
                ng = d + timedelta(days=k * huong)
                if ng < hom_nay:
                    # Kéo lên quá khứ thì vô nghĩa.
                    continue
                diem, _kh, nen = self._diem_ngay(luat, ng)
                if diem < diem_goc:
                    # Khoá sắp: điểm thấp nhất, rồi ngày sớm, rồi mùa
                    # nên làm. "Nên làm" chỉ là tiêu chí cuối.
                    ung_vien.append((diem, 0 if huong < 0 else 1,
                                     0 if nen else 1, ng, k * huong))
            if not ung_vien:
                continue
            _d, _h, _n, ng, doi = min(ung_vien)
            huong_chu = _('kéo lên sớm') if doi < 0 else _('đẩy lùi')
            canh = ''
            if doi > 0:
                canh = _(
                    ' Lưu ý đây là ĐẨY LÙI: không tìm được ngày sớm hơn '
                    'nào ra khỏi mùa, nên thiết bị sẽ chạy thêm %d ngày '
                    'quá chu kỳ thiết kế.') % doi
            return ng, doi, _(
                'Hạn %(h)s rơi vào %(m)s. Đề xuất %(hg)s %(n)d ngày, làm '
                'ngày %(ng)s.%(c)s',
                h=d, m=ten_mua(khop_goc), hg=huong_chu, n=abs(doi),
                ng=ng, c=canh), True

        return d, 0, _(
            'Hạn rơi vào %(m)s và KHÔNG tránh được trong giới hạn %(c)d '
            'ngày. Phải bố trí làm trong mùa — xem lý do ở luật mùa để '
            'chuẩn bị.', m=ten_mua(khop_goc), c=cap), False
