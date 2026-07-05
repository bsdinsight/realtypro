# -*- coding: utf-8 -*-
"""Roll-up chi phí thực (AC) theo hạng mục từ dòng hóa đơn nhà thầu."""
from odoo import api, fields, models


class RpStructure(models.Model):
    _inherit = 'rp.structure'

    actual_move_line_ids = fields.One2many(
        'account.move.line', 'structure_id',
        string='Dòng chi phí thực')
    cost_allocation_ids = fields.One2many(
        'rp.cost.allocation', 'structure_id',
        string='Phân bổ chi phí (split)')
    actual_cost = fields.Monetary(
        string='Chi phí thực (AC)',
        compute='_compute_actual_cost', store=True,
        currency_field='currency_id',
        help='Σ giá trị (chưa thuế) chi phí ĐÃ POSTED gắn hạng mục này: '
             'dòng hóa đơn trực tiếp (khi KHÔNG split) + phân bổ split. '
             'in_invoice cộng, in_refund trừ. Nguồn AC cho EVM.')

    @api.depends('actual_move_line_ids.price_subtotal',
                 'actual_move_line_ids.parent_state',
                 'actual_move_line_ids.move_id.move_type',
                 'actual_move_line_ids.cost_allocation_ids.amount',
                 'cost_allocation_ids.amount',
                 'cost_allocation_ids.parent_state',
                 'cost_allocation_ids.move_line_id.move_id.move_type')
    def _compute_actual_cost(self):
        for rec in self:
            total = 0.0
            # Dòng hóa đơn gắn trực tiếp — CHỈ khi dòng không bị split
            for line in rec.actual_move_line_ids:
                if line.parent_state != 'posted':
                    continue
                if line.cost_allocation_ids:
                    continue  # đã split → tính theo allocation bên dưới
                move_type = line.move_id.move_type
                if move_type == 'in_invoice':
                    total += line.price_subtotal
                elif move_type == 'in_refund':
                    total -= line.price_subtotal
            # Phân bổ split trỏ vào hạng mục này
            for alloc in rec.cost_allocation_ids:
                if alloc.parent_state != 'posted':
                    continue
                move_type = alloc.move_line_id.move_id.move_type
                if move_type == 'in_invoice':
                    total += alloc.amount
                elif move_type == 'in_refund':
                    total -= alloc.amount
            rec.actual_cost = total
