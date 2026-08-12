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

    # ⚠ KHÔNG chặn khi tổng phân bổ vượt hạn mức facility — anh Đại chốt
    # 2026-07-29 là CẢNH BÁO MỀM (thực tế cần phân bổ tạm rồi điều chỉnh,
    # và hạn mức hay được cấp trước khi ký đủ hợp đồng). Cảnh báo hiển thị
    # bằng `amount_unallocated` âm: tô đỏ trên form facility + list trong
    # HĐTD + alert trong tab Phân bổ dự án.
