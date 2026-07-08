# -*- coding: utf-8 -*-
"""Bổ sung tham chiếu Khả dụng thực tế (borrowing base) vào wizard phân
bổ lại hạn mức — để user đối chiếu hạn mức hợp đồng với trần TSBĐ."""
from odoo import api, fields, models


class ReLoanFacilityReallocateWizard(models.TransientModel):
    _inherit = 're.loan.facility.reallocate.wizard'

    available_effective = fields.Monetary(
        string='Khả dụng thực tế (theo TSBĐ)',
        compute='_compute_available_effective',
        help='Trần rút thực tế của HĐTD theo cơ sở bảo đảm (borrowing '
             'base). Hạn mức hợp đồng có thể lớn hơn số này — phần vượt '
             'chỉ rút được khi bổ sung TSBĐ / nghiệm thu thêm với CĐT.')
    over_borrowing_base = fields.Boolean(
        compute='_compute_available_effective',
        help='Tổng hạn mức mới vượt khả dụng thực tế theo TSBĐ.')

    @api.depends('amount_total_new', 'contract_id')
    def _compute_available_effective(self):
        for rec in self:
            eff = rec.contract_id.amount_available_effective \
                + rec.contract_id.amount_used_total
            # eff = base tổng (khả dụng + đã dùng) ~ trần hạn mức theo TSBĐ
            rec.available_effective = eff
            rec.over_borrowing_base = (
                rec.contract_id.has_any_pledges
                and rec.amount_total_new > eff + 0.01)
