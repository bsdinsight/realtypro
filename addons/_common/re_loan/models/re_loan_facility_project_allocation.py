# -*- coding: utf-8 -*-
"""
Phân bổ hạn mức Facility theo Dự án.

Mỗi facility = 1 mục đích sử dụng vốn (purpose). Phân bổ tiếp xuống
từng dự án (re.project). VD HĐTD 100 tỷ, facility "GPMB" 40 tỷ →
phân Dự án A: 30 tỷ + Dự án B: 10 tỷ. Σ phân bổ ≤ amount_limit.

Đây là PLAN/budget level (kế hoạch). Khác với rp.loan.allocation
(bridge L5) chỉ phân bổ THỰC TẾ theo từng KW.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ReLoanFacilityProjectAllocation(models.Model):
    _name = 're.loan.facility.project.allocation'
    _description = 'Phân bổ hạn mức Facility theo dự án'
    _order = 'facility_id, project_id, id'

    facility_id = fields.Many2one(
        're.loan.facility', string='Hạn mức (Facility)', required=True,
        ondelete='cascade', index=True)
    project_id = fields.Many2one(
        're.project', string='Dự án', required=True,
        ondelete='restrict', index=True)
    amount = fields.Monetary(string='Số tiền phân bổ', required=True)
    description = fields.Char(string='Diễn giải')

    currency_id = fields.Many2one(
        related='facility_id.currency_id', store=True, readonly=True)
    company_id = fields.Many2one(
        related='facility_id.company_id', store=True, readonly=True)
    # Related cho pivot/group-by
    purpose = fields.Selection(
        related='facility_id.purpose', store=True, readonly=True,
        string='Mục đích sử dụng vốn')
    credit_contract_id = fields.Many2one(
        related='facility_id.credit_contract_id', store=True, readonly=True,
        string='HĐTD')

    @api.constrains('amount')
    def _check_amount(self):
        for rec in self:
            if rec.amount < 0:
                raise ValidationError(_(
                    "Số tiền phân bổ không được âm."))

    @api.constrains('amount', 'facility_id')
    def _check_total_within_facility(self):
        for rec in self:
            fac = rec.facility_id
            total = sum(fac.project_allocation_ids.mapped('amount'))
            if total > fac.amount_limit + 1:  # tolerance VND
                raise ValidationError(_(
                    "Tổng phân bổ theo dự án (%(t)s) vượt hạn mức "
                    "facility '%(f)s' (%(l)s).",
                    t=total, f=fac.name, l=fac.amount_limit))

    @api.model_create_multi
    def create(self, vals_list):
        # @api.constrains on O2M không fire khi create từ phía child
        # → check tường minh.
        recs = super().create(vals_list)
        recs._check_total_within_facility()
        return recs
