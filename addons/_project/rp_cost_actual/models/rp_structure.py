# -*- coding: utf-8 -*-
"""Roll-up chi phí thực (AC) theo hạng mục từ dòng hóa đơn nhà thầu."""
from odoo import api, fields, models


class RpStructure(models.Model):
    _inherit = 'rp.structure'

    actual_move_line_ids = fields.One2many(
        'account.move.line', 'structure_id',
        string='Dòng chi phí thực')
    actual_cost = fields.Monetary(
        string='Chi phí thực (AC)',
        compute='_compute_actual_cost', store=True,
        currency_field='currency_id',
        help='Σ giá trị (chưa thuế) các dòng hóa đơn nhà thầu ĐÃ POSTED '
             'gắn hạng mục này: in_invoice cộng, in_refund trừ. Nguồn AC '
             'cho EVM — CPI = EV / AC.')

    @api.depends('actual_move_line_ids.price_subtotal',
                 'actual_move_line_ids.parent_state',
                 'actual_move_line_ids.move_id.move_type')
    def _compute_actual_cost(self):
        for rec in self:
            total = 0.0
            for line in rec.actual_move_line_ids:
                if line.parent_state != 'posted':
                    continue
                move_type = line.move_id.move_type
                if move_type == 'in_invoice':
                    total += line.price_subtotal
                elif move_type == 'in_refund':
                    total -= line.price_subtotal
            rec.actual_cost = total
