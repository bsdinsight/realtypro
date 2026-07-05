# -*- coding: utf-8 -*-
"""Phân bổ 1 dòng hóa đơn cho NHIỀU đầu việc (split AC).

Dùng khi 1 dòng chi phí trên hóa đơn nhà thầu phục vụ nhiều hạng mục
(vd "Thuê cẩu tháp tháng 6" chia cho Tầng hầm + Phần thân). Khi dòng
hóa đơn CÓ allocation → AC tính theo allocation (bỏ qua structure_id
trực tiếp trên dòng); KHÔNG có allocation → AC theo structure_id dòng.
"""
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class RpCostAllocation(models.Model):
    _name = 'rp.cost.allocation'
    _description = 'Phân bổ chi phí hóa đơn theo đầu việc'
    _order = 'move_line_id, id'

    move_line_id = fields.Many2one(
        'account.move.line', string='Dòng hóa đơn',
        required=True, ondelete='cascade', index=True,
        domain="[('move_id.move_type', 'in', ('in_invoice', 'in_refund')),"
               " ('display_type', '=', 'product')]")
    move_id = fields.Many2one(
        related='move_line_id.move_id', store=True, index=True,
        string='Hóa đơn')
    parent_state = fields.Selection(
        related='move_line_id.parent_state', store=True)
    structure_id = fields.Many2one(
        'rp.structure', string='Hạng mục (đầu việc)',
        required=True, ondelete='restrict', index=True)
    cost_category_id = fields.Many2one(
        'rp.cost.category', string='Nhóm chi phí', ondelete='restrict')
    amount = fields.Monetary(
        string='Số tiền phân bổ', required=True,
        currency_field='currency_id',
        help='Phần giá trị (chưa thuế) của dòng hóa đơn phân bổ cho '
             'hạng mục này.')
    note = fields.Char(string='Ghi chú')
    currency_id = fields.Many2one(
        related='move_line_id.currency_id', store=True)
    company_id = fields.Many2one(
        related='move_line_id.company_id', store=True)

    @api.constrains('amount', 'move_line_id')
    def _check_amount(self):
        for rec in self:
            if rec.amount <= 0:
                raise ValidationError('Số tiền phân bổ phải > 0.')
            line = rec.move_line_id
            total = sum(line.cost_allocation_ids.mapped('amount'))
            if total > abs(line.price_subtotal) + 0.01:
                raise ValidationError(
                    'Tổng phân bổ (%(t)s) vượt giá trị dòng hóa đơn '
                    '"%(l)s" (%(s)s).' % {
                        't': '{:,.0f}'.format(total),
                        'l': line.name or line.move_id.name,
                        's': '{:,.0f}'.format(abs(line.price_subtotal))})
