# -*- coding: utf-8 -*-
"""Facility: base riêng (ring-fence) + khả dụng thực tế 3-min."""
from odoo import api, fields, models


class ReLoanFacility(models.Model):
    _inherit = 're.loan.facility'

    facility_pledge_ids = fields.One2many(
        're.loan.collateral.pledge', 'facility_id',
        string='TSBĐ riêng facility',
        domain=[('pledge_target', '=', 'facility')])
    borrowing_base_own = fields.Monetary(
        string='Base riêng (TSBĐ facility)',
        compute='_compute_borrowing_base', store=True,
        help='Σ đóng góp của các pledge gắn RIÊNG facility này '
             '(ring-fence — vd quyền đòi nợ dự án của chính facility).')
    has_own_pledges = fields.Boolean(
        compute='_compute_borrowing_base', store=True)
    amount_available_effective = fields.Monetary(
        string='Khả dụng thực tế',
        compute='_compute_available_effective',
        help='= min(① HM − dư nợ facility; ② base riêng − dư nợ '
             '(khi có TSBĐ riêng); ③ base toàn HĐTD − dư nợ toàn '
             'HĐTD). Floor 0. Số RÚT ĐƯỢC thực tế hôm nay.')
    margin_call = fields.Boolean(
        string='Cảnh báo thiếu bảo đảm',
        compute='_compute_available_effective',
        help='Dư nợ facility đã vượt base riêng — NH sẽ yêu cầu bổ '
             'sung TSBĐ hoặc trả bớt nợ (margin call).')

    @api.depends('facility_pledge_ids.base_contribution',
                 'facility_pledge_ids.state',
                 'facility_pledge_ids.pledge_target')
    def _compute_borrowing_base(self):
        for rec in self:
            # Chỉ pledge ĐÃ KHAI tỷ lệ cho vay — pledge cũ chưa khai
            # (rate=0) không kích hoạt ràng buộc base (tránh margin
            # call giả trên dữ liệu có sẵn).
            pledges = rec.facility_pledge_ids.filtered(
                lambda p: p.state == 'active'
                and p.pledge_target == 'facility'
                and p.advance_rate)
            rec.borrowing_base_own = sum(
                pledges.mapped('base_contribution'))
            rec.has_own_pledges = bool(pledges)

    def _compute_available_effective(self):
        for rec in self:
            contract = rec.credit_contract_id
            candidates = [rec.amount_limit - rec.amount_used]
            if rec.has_own_pledges:
                candidates.append(
                    rec.borrowing_base_own - rec.amount_used)
            if contract and contract.has_any_pledges:
                candidates.append(
                    contract.borrowing_base_total
                    - contract.amount_used_total)
            rec.amount_available_effective = max(0.0, min(candidates))
            rec.margin_call = (
                rec.has_own_pledges
                and rec.amount_used > rec.borrowing_base_own + 0.01)
