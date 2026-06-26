# -*- coding: utf-8 -*-
"""Inherit account.move: cấn trừ Tạm ứng vào vendor bill.

Vendor bill có thể được cấn trừ bởi nhiều Tạm ứng đã thanh toán.
Field amount_residual_after_advance = amount_residual - Σ settlements.

KHÔNG modify amount_residual gốc (Odoo accounting logic). Chỉ tính
song song để hiển thị "Số HĐ thực tế còn phải trả sau khi cấn trừ
tạm ứng" — dùng cho dossier validation.
"""
from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    advance_settlement_ids = fields.One2many(
        'rp.advance.settlement', 'invoice_id',
        string='Cấn trừ Tạm ứng',
        readonly=False)
    advance_settlement_count = fields.Integer(
        compute='_compute_advance_settlement_stats', store=True)
    amount_advance_settled = fields.Monetary(
        string='Đã cấn trừ tạm ứng',
        compute='_compute_advance_settlement_stats', store=True,
        help='Tổng số tiền tạm ứng đã được cấn trừ vào hóa đơn này.')
    amount_residual_after_advance = fields.Monetary(
        string='Còn phải trả (sau cấn trừ)',
        compute='_compute_advance_settlement_stats', store=True,
        help='Số tiền hóa đơn còn phải trả SAU khi đã cấn trừ tạm ứng. '
             '= amount_residual − Đã cấn trừ tạm ứng. KW giải ngân '
             'tiếp theo nên chỉ trả số này.')

    @api.depends('advance_settlement_ids.amount', 'amount_residual')
    def _compute_advance_settlement_stats(self):
        for rec in self:
            settled = sum(rec.advance_settlement_ids.mapped('amount'))
            rec.advance_settlement_count = len(rec.advance_settlement_ids)
            rec.amount_advance_settled = settled
            rec.amount_residual_after_advance = max(
                0.0, rec.amount_residual - settled)

    def action_view_advance_settlements(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Cấn trừ tạm ứng — %s' % (self.name or ''),
            'res_model': 'rp.advance.settlement',
            'view_mode': 'list,form',
            'domain': [('invoice_id', '=', self.id)],
            'context': {'default_invoice_id': self.id},
        }
