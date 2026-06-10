# -*- coding: utf-8 -*-
"""
Khối lượng (BOQ) — dòng chi tiết HĐ nhà thầu.

Optional: nếu HĐ trọn gói có thể không cần line; nếu nhập line thì Σ ≈ giá
trị HĐ trước thuế (constraint nhẹ ở contract).
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class RpContractLine(models.Model):
    _name = 'rp.contract.line'
    _description = 'Khối lượng HĐ nhà thầu'
    _order = 'contract_id, sequence, id'

    contract_id = fields.Many2one(
        'rp.contract', string='HĐ', required=True, ondelete='cascade',
        index=True)
    sequence = fields.Integer(default=10)
    structure_id = fields.Many2one(
        'rp.structure', string='Hạng mục',
        domain="[('project_id','=',parent.project_id)]",
        help='Hạng mục cover bởi dòng (tuỳ chọn).')
    description = fields.Char(string='Mô tả', required=True)
    unit_of_measure = fields.Char(
        string='ĐVT', help='Đơn vị: m, m², m³, tấn, bộ, kg...')
    quantity = fields.Float(string='Khối lượng', digits=(16, 3))
    unit_price = fields.Monetary(string='Đơn giá')
    amount = fields.Monetary(
        string='Thành tiền', compute='_compute_amount', store=True)
    note = fields.Char(string='Ghi chú')

    project_id = fields.Many2one(
        related='contract_id.project_id', store=True, readonly=True)
    currency_id = fields.Many2one(
        related='contract_id.currency_id', store=True, readonly=True)
    company_id = fields.Many2one(
        related='contract_id.company_id', store=True, readonly=True)

    @api.depends('quantity', 'unit_price')
    def _compute_amount(self):
        for rec in self:
            rec.amount = rec.quantity * rec.unit_price

    @api.constrains('quantity', 'unit_price')
    def _check_nonneg(self):
        for rec in self:
            if rec.quantity < 0 or rec.unit_price < 0:
                raise ValidationError(_(
                    "Khối lượng / Đơn giá không được âm."))
