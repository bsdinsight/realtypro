# -*- coding: utf-8 -*-
"""HĐTD: base tổng (umbrella) + khả dụng + margin call toàn gói."""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ReLoanCreditContract(models.Model):
    _inherit = 're.loan.credit.contract'

    all_pledge_ids = fields.One2many(
        're.loan.collateral.pledge', 'credit_contract_id',
        string='Toàn bộ pledge (mọi cấp)')
    borrowing_base_total = fields.Monetary(
        string='Cơ sở bảo đảm (base tổng)',
        compute='_compute_borrowing_base_total', store=True,
        help='Σ đóng góp của MỌI pledge đang thế chấp thuộc HĐTD '
             '(cấp HĐTD + facility + KW) = trần theo tài sản.')
    has_any_pledges = fields.Boolean(
        compute='_compute_borrowing_base_total', store=True)
    amount_used_total = fields.Monetary(
        string='Tổng dư nợ đã dùng',
        compute='_compute_used_total',
        help='Σ đã sử dụng của các facility dưới HĐTD.')
    amount_available_effective = fields.Monetary(
        string='Khả dụng thực tế (HĐTD)',
        compute='_compute_available_effective',
        help='= min(Tổng hạn mức, Cơ sở bảo đảm) − tổng dư nợ. '
             'Floor 0. Không có pledge nào → bỏ ràng buộc base.')
    margin_call = fields.Boolean(
        string='Cảnh báo thiếu bảo đảm (HĐTD)',
        compute='_compute_available_effective',
        help='Tổng dư nợ vượt cơ sở bảo đảm toàn HĐTD.')
    unrated_pledge_count = fields.Integer(
        string='Pledge chưa khai tỷ lệ',
        compute='_compute_unrated_pledges',
        help='Số TSBĐ đang thế chấp nhưng CHƯA khai Tỷ lệ cho vay (%) '
             '— chưa tham gia cơ sở bảo đảm, định giá lại các TS này '
             'không ảnh hưởng khả dụng.')

    @api.depends('all_pledge_ids.state', 'all_pledge_ids.advance_rate')
    def _compute_unrated_pledges(self):
        for rec in self:
            rec.unrated_pledge_count = len(rec.all_pledge_ids.filtered(
                lambda p: p.state == 'active' and not p.advance_rate))

    @api.constrains('amount_facility_total', 'borrowing_base_total',
                    'has_any_pledges')
    def _check_facility_within_base(self):
        """CHẶN CỨNG: Σ hạn mức facility ≤ Cơ sở bảo đảm (base tổng).

        Chỉ áp khi HĐTD ĐÃ khai TSĐB có tỷ lệ (has_any_pledges) — chưa
        khai thì base = 0, không chặn (tránh khóa HĐTD chưa cấu hình).
        Ràng buộc Σ ≤ Tổng hạn mức HĐTD do re_loan core lo riêng.
        Fire cả khi sửa hạn mức facility (amount_facility_total) lẫn khi
        định giá lại làm base đổi (borrowing_base_total)."""
        for rec in self:
            if not rec.has_any_pledges:
                continue
            if rec.currency_id.compare_amounts(
                    rec.amount_facility_total,
                    rec.borrowing_base_total) > 0:
                raise ValidationError(_(
                    "Tổng hạn mức các facility (%(f)s) vượt Cơ sở bảo "
                    "đảm theo TSĐB (%(b)s).\n\nGiảm phân bổ hạn mức "
                    "facility, hoặc bổ sung / định giá lại TSĐB để tăng "
                    "cơ sở bảo đảm. Có thể chỉnh hạn mức facility ngay "
                    "trong màn hình 'Định giá lại' hoặc 'Phân bổ lại "
                    "hạn mức'.",
                    f='{:,.0f}'.format(rec.amount_facility_total),
                    b='{:,.0f}'.format(rec.borrowing_base_total)))

    @api.depends('all_pledge_ids.base_contribution',
                 'all_pledge_ids.state')
    def _compute_borrowing_base_total(self):
        for rec in self:
            # Chỉ pledge đã khai tỷ lệ (xem ghi chú ở facility).
            pledges = rec.all_pledge_ids.filtered(
                lambda p: p.state == 'active' and p.advance_rate)
            rec.borrowing_base_total = sum(
                pledges.mapped('base_contribution'))
            rec.has_any_pledges = bool(pledges)

    @api.depends('facility_ids.amount_used')
    def _compute_used_total(self):
        for rec in self:
            rec.amount_used_total = sum(
                rec.facility_ids.mapped('amount_used'))

    @api.depends('amount_total', 'amount_used_total',
                 'has_any_pledges', 'borrowing_base_total')
    def _compute_available_effective(self):
        for rec in self:
            used = rec.amount_used_total
            candidates = [rec.amount_total - used]
            if rec.has_any_pledges:
                candidates.append(rec.borrowing_base_total - used)
            rec.amount_available_effective = max(0.0, min(candidates))
            rec.margin_call = (
                rec.has_any_pledges
                and used > rec.borrowing_base_total + 0.01)
