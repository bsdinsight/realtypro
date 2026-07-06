# -*- coding: utf-8 -*-
"""HĐTD: base tổng (umbrella) + khả dụng + margin call toàn gói."""
from odoo import api, fields, models


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

    def _compute_used_total(self):
        for rec in self:
            rec.amount_used_total = sum(
                rec.facility_ids.mapped('amount_used'))

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
