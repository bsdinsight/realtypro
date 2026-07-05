# -*- coding: utf-8 -*-
"""Gắn dòng chi phí hóa đơn nhà thầu vào WBS (hạng mục × nhóm chi phí).

Nguồn AC (Actual Cost) cho EVM. Chỉ có ý nghĩa với vendor bill
(move_type in_invoice/in_refund); dòng bán hàng / bút toán khác để trống.
"""
from odoo import fields, models


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    structure_id = fields.Many2one(
        'rp.structure', string='Hạng mục (đầu việc)', index=True,
        help='Hạng mục/đầu việc mà dòng chi phí này thuộc về. Dùng để '
             'roll-up chi phí thực (AC) theo WBS phục vụ EVM '
             '(CPI = EV/AC). Áp dụng cho dòng hóa đơn nhà thầu.')
    cost_category_id = fields.Many2one(
        'rp.cost.category', string='Nhóm chi phí', index=True,
        help='Nhóm chi phí của dòng chi phí thực (chiều phân loại AC, '
             'đối chiếu với dự toán cùng nhóm).')
    cost_allocation_ids = fields.One2many(
        'rp.cost.allocation', 'move_line_id',
        string='Phân bổ nhiều đầu việc',
        help='Chia dòng chi phí này cho NHIỀU hạng mục. Khi có phân bổ '
             '→ AC tính theo phân bổ, bỏ qua "Hạng mục (AC)" trên dòng.')
    cost_allocation_count = fields.Integer(
        compute='_compute_cost_allocation_count')

    def _compute_cost_allocation_count(self):
        for line in self:
            line.cost_allocation_count = len(line.cost_allocation_ids)
