# -*- coding: utf-8 -*-
"""Độ tin cậy và KPI bảo trì theo kỳ — D11 và F15.

Hai chỉ số này rất dễ ra số đẹp mà sai, nên model lưu CẢ TỬ SỐ LẪN MẪU
SỐ chứ không chỉ kết quả. Ai cãi con số thì mở ra đối chiếu được, không
phải tin vào một ô duy nhất.

Ba quyết định định nghĩa — chỗ sai thì cả chỉ số vô nghĩa
----------------------------------------------------------
**① MTBF chia cho GIỜ MÁY CHẠY, không phải giờ theo lịch.** Tua-bin gió
đứng yên phần lớn thời gian vì gió, vì cắt giảm, vì bảo trì. Lấy giờ
lịch làm tử số thì MTBF của một máy hay hỏng mà ít chạy trông còn đẹp
hơn máy chạy khoẻ. Nguồn là đồng hồ ``operating_hours``; **không có
đồng hồ thì trả N/A**, tuyệt đối không âm thầm thay bằng giờ lịch.

**② MTTR KHÔNG tính thời gian chờ.** ``duration_hours`` của lệnh gồm cả
quãng ``is_on_hold`` — chờ cẩu, chờ vật tư, chờ lặng gió. Đó là bài toán
hậu cần, không phải tay nghề thợ sửa. Gộp vào MTTR là đổ lỗi nhầm người.
Nên MTTR = thời lượng − giờ chờ, còn **MDT** (thời gian máy nằm) để
riêng. Khoảng cách giữa hai số chính là chi phí hậu cần.

**③ Số lần hỏng lấy từ cờ ``is_failure`` KHAI TAY.** Không suy từ "có
lệnh công việc": nhiều lần dừng chỉ cần khởi động lại từ xa — có dừng,
không hỏng. Suy kiểu đó làm MTBF đẹp hơn thực tế, tức sai về phía nguy
hiểm.

Mẫu số bằng 0 trả **False (N/A)**, không trả 0 — "chưa hỏng lần nào"
khác hẳn "hỏng liên tục".
"""
from odoo import _, api, fields, models


class EamReliability(models.Model):
    _name = 'eam.reliability'
    _description = 'Độ tin cậy & KPI bảo trì theo kỳ'
    _order = 'date_to desc, asset_id'
    _rec_name = 'display_name'

    asset_id = fields.Many2one(
        'eam.asset', string='Tài sản', required=True, ondelete='cascade',
        index=True)
    location_id = fields.Many2one(
        'eam.location', string='Vị trí',
        related='asset_id.current_location_id', store=True, index=True,
        help='Vị trí ĐANG lắp. Cấu phần quay vòng có thể đã chuyển máy '
             'trong kỳ — khi đó giờ máy chạy lấy theo vị trí hiện tại là '
             'xấp xỉ, không phải chính xác.')
    date_from = fields.Date(string='Từ ngày', required=True)
    date_to = fields.Date(string='Đến ngày', required=True)
    company_id = fields.Many2one(
        'res.company', string='Công ty',
        default=lambda self: self.env.company)

    # ── Tử số / mẫu số: lưu để đối chiếu, không chỉ lưu kết quả ──────
    operating_hours = fields.Float(
        string='Giờ máy chạy trong kỳ', digits=(16, 1),
        help='Chênh lệch đồng hồ giờ máy chạy. Đây là TỬ SỐ của MTBF.')
    has_meter = fields.Boolean(
        string='Có đồng hồ giờ chạy',
        help='Không có thì MTBF để trống — không thay bằng giờ lịch.')
    meter_gap_count = fields.Integer(
        string='Đoạn đồng hồ bỏ qua',
        help='Số đoạn đọc bị loại vì đi lùi hoặc vượt thời gian thực '
             'trôi. Lớn hơn 0 nghĩa là giờ máy chạy ĐANG THIẾU, và MTBF '
             'theo đó thấp hơn thực tế.')
    failure_count = fields.Integer(
        string='Số lần hỏng',
        help='Đếm lệnh khai is_failure. MẪU SỐ của MTBF và MTTR.')
    repair_hours = fields.Float(
        string='Giờ sửa thực', digits=(16, 1),
        help='Thời lượng lệnh TRỪ giờ chờ.')
    hold_hours = fields.Float(
        string='Giờ chờ', digits=(16, 1),
        help='Chờ cẩu, chờ vật tư, chờ thời tiết.')
    downtime_hours = fields.Float(
        string='Giờ máy nằm', digits=(16, 1),
        help='Từ sổ dừng máy, chỉ các khoảng tính là dừng.')

    # ── Chỉ số ──────────────────────────────────────────────────────
    mtbf_hours = fields.Float(
        string='MTBF (giờ chạy)', digits=(16, 1), compute='_compute_kpi',
        store=True)
    mttr_hours = fields.Float(
        string='MTTR (giờ sửa)', digits=(16, 1), compute='_compute_kpi',
        store=True)
    mdt_hours = fields.Float(
        string='MDT (giờ nằm)', digits=(16, 1), compute='_compute_kpi',
        store=True)
    wait_share = fields.Float(
        string='% thời gian nằm là CHỜ', digits=(16, 1),
        compute='_compute_kpi', store=True,
        help='Phần máy nằm mà không ai đang sửa. Cao thì vấn đề ở hậu '
             'cần chứ không ở tay nghề.')
    kpi_note = fields.Char(string='Vì sao để trống', compute='_compute_kpi',
                           store=True)

    # ── F15: KPI bảo trì ────────────────────────────────────────────
    wo_pm_count = fields.Integer(string='Lệnh phòng ngừa')
    wo_cm_count = fields.Integer(string='Lệnh khắc phục')
    pm_ratio = fields.Float(
        string='% phòng ngừa', digits=(16, 1), compute='_compute_kpi',
        store=True,
        help='Phòng ngừa trên tổng phòng ngừa + khắc phục. Thấp nghĩa là '
             'đang chạy theo sự cố.')
    detect_early_count = fields.Integer(
        string='Bắt được sớm',
        help='Hỏng phát hiện qua giám sát trạng thái, đo rung hoặc kiểm '
             'tra định kỳ — tức TRƯỚC khi mất sản lượng.')
    detect_early_pct = fields.Float(
        string='% bắt được sớm', digits=(16, 1), compute='_compute_kpi',
        store=True,
        help='Câu đắt nhất của bảo trì: giám sát trạng thái chỉ đáng tiền '
             'khi tỷ lệ này cao.')
    cost_total = fields.Monetary(string='Chi phí bảo trì')
    currency_id = fields.Many2one(
        'res.currency', default=lambda self: self.env.company.currency_id)

    display_name = fields.Char(compute='_compute_display_name')

    # ------------------------------------------------------------------
    @api.depends('asset_id', 'date_from', 'date_to')
    def _compute_display_name(self):
        for r in self:
            r.display_name = '%s · %s → %s' % (
                r.asset_id.display_name or '?', r.date_from or '?',
                r.date_to or '?')

    @api.depends('operating_hours', 'failure_count', 'repair_hours',
                 'meter_gap_count',
                 'downtime_hours', 'hold_hours', 'has_meter',
                 'wo_pm_count', 'wo_cm_count', 'detect_early_count')
    def _compute_kpi(self):
        for r in self:
            ly_do = []
            # MTBF
            if not r.failure_count:
                r.mtbf_hours = 0.0
                ly_do.append(_('chưa hỏng lần nào nên chưa có MTBF'))
            elif not r.has_meter:
                r.mtbf_hours = 0.0
                ly_do.append(_('không có đồng hồ giờ máy chạy'))
            else:
                r.mtbf_hours = r.operating_hours / r.failure_count
            # MTTR / MDT. Giờ sửa bằng 0 mà vẫn có hỏng nghĩa là KHÔNG
            # AI GHI giờ sửa — khác hẳn "sửa tức thì". Trả về rỗng kèm lý
            # do, vì một MTTR = 0,0 giờ cạnh MDT = 163 giờ là con số làm
            # người đọc hiểu ngược: tưởng sửa nhanh, thực ra là mất dữ
            # liệu.
            if r.failure_count and r.repair_hours:
                r.mttr_hours = r.repair_hours / r.failure_count
            else:
                r.mttr_hours = 0.0
                if r.failure_count:
                    ly_do.append(_('chưa ghi giờ sửa nên chưa có MTTR'))
            r.mdt_hours = (r.downtime_hours / r.failure_count
                           if r.failure_count else 0.0)
            r.wait_share = (r.hold_hours * 100.0 / r.downtime_hours
                            if r.downtime_hours else 0.0)
            tong = r.wo_pm_count + r.wo_cm_count
            r.pm_ratio = (r.wo_pm_count * 100.0 / tong) if tong else 0.0
            r.detect_early_pct = (r.detect_early_count * 100.0 /
                                  r.failure_count) if r.failure_count else 0.0
            r.kpi_note = '; '.join(ly_do) or False

    # ------------------------------------------------------------------
    @api.model
    def _gio_may_chay(self, asset, tu, den):
        """Chênh lệch đồng hồ giờ máy chạy trong kỳ.

        Trả ``(giờ, có_đồng_hồ)``. Đồng hồ đi LÙI (thay thiết bị, reset)
        thì bỏ qua đoạn đó thay vì cộng một số âm — số âm ở đây làm MTBF
        vọt lên vô lý mà không ai thấy.
        """
        R = self.env['eam.meter.reading']
        # Đồng hồ gắn theo VỊ TRÍ, không theo tài sản — cấu phần quay
        # vòng chuyển máy giữa kỳ thì số này là xấp xỉ. Ghi rõ còn hơn
        # im lặng đưa ra một con số trông như chính xác.
        dh = self.env['eam.meter'].search([
            ('location_id', '=', asset.current_location_id.id),
            ('meter_type', '=', 'operating_hours')], limit=1)
        if not dh:
            return 0.0, False, 0
        rs = R.search([('meter_id', '=', dh.id),
                       ('date', '>=', tu), ('date', '<=', den)],
                      order='date')
        if len(rs) < 2:
            return 0.0, bool(dh), 0
        tong, ngo = 0.0, 0
        for x, y in zip(rs, rs[1:]):
            chenh = (y.effective_value or 0.0) - (x.effective_value or 0.0)
            # Giờ máy chạy KHÔNG THỂ vượt thời gian thực trôi giữa hai lần
            # đọc. Đây là chốt chặn chịu lực nhất của cả bộ chỉ số: một số
            # đọc sai (đọc nhầm máy, gõ thiếu chữ số) làm số sau nó nhảy
            # vọt, và nếu cứ cộng thì ra những con số tự nó vô lý — T08
            # từng ra 11.261 giờ chạy trong một năm chỉ có 8.760 giờ.
            troi = (y.date - x.date).total_seconds() / 3600.0 \
                if hasattr(y.date, 'total_seconds') else \
                (y.date - x.date).days * 24.0
            if chenh < 0:
                # Đồng hồ đi lùi: thay thiết bị hoặc đặt lại. Bỏ đoạn này
                # chứ không cộng số âm.
                ngo += 1
                continue
            if troi > 0 and chenh > troi * 1.05:
                ngo += 1
                continue
            tong += chenh
        return tong, True, ngo

    @api.model
    def tinh_ky(self, tu, den, assets=None):
        """Dựng lại chỉ số cho một kỳ. Chạy lại bao nhiêu lần cũng ra một."""
        A = assets or self.env['eam.asset'].search(
            [('current_location_id', '!=', False)])
        W = self.env['eam.work.order']
        O = self.env['eam.outage']
        SOM = ('condition', 'inspection')   # bắt được TRƯỚC khi mất sản lượng
        ra = self.browse()
        for a in A:
            mien = [('asset_id', '=', a.id),
                    ('date_planned_start', '>=', tu),
                    ('date_planned_start', '<=', den)]
            ls = W.search(mien)
            hong = ls.filtered('is_failure')
            dung = O.search([('asset_id', '=', a.id),
                             ('counts_as_downtime', '=', True),
                             ('date_start', '>=', tu),
                             ('date_start', '<=', den)])
            gio, co_dh, ngo = self._gio_may_chay(a, tu, den)
            cho = sum(hong.mapped('hold_hours'))
            vals = {
                'asset_id': a.id, 'date_from': tu, 'date_to': den,
                'operating_hours': gio, 'has_meter': co_dh,
                'meter_gap_count': ngo,
                'failure_count': len(hong),
                # Giờ sửa THỰC = thời lượng trừ giờ chờ, không bao giờ âm.
                'repair_hours': sum(
                    max((w.duration_hours or 0.0) - (w.hold_hours or 0.0), 0.0)
                    for w in hong),
                'hold_hours': cho,
                'downtime_hours': sum(dung.mapped('duration_hours')),
                'wo_pm_count': len(ls.filtered(
                    lambda w: w.work_type in ('preventive', 'predictive'))),
                'wo_cm_count': len(ls.filtered(
                    lambda w: w.work_type == 'corrective')),
                'detect_early_count': len(hong.filtered(
                    lambda w: w.detection_method in SOM)),
                'cost_total': sum(ls.mapped('cost_total')),
            }
            # Tài sản không có hoạt động gì trong kỳ thì KHÔNG dựng
            # dòng. Bảng 966 dòng mà 956 dòng toàn số 0 thì không ai đọc,
            # và cái cần nhìn — máy nào đang hỏng nhiều — bị chôn mất.
            co_viec = (vals['failure_count'] or vals['wo_pm_count']
                       or vals['wo_cm_count'] or vals['downtime_hours'])
            cu = self.search([('asset_id', '=', a.id),
                              ('date_from', '=', tu), ('date_to', '=', den)],
                             limit=1)
            if not co_viec:
                if cu:
                    cu.unlink()
                continue
            if cu:
                cu.write(vals)
                ra |= cu
            else:
                ra |= self.create(vals)
        return ra
