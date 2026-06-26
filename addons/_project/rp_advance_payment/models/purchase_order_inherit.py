# -*- coding: utf-8 -*-
"""Inherit purchase.order: thêm tab Tạm ứng + thống kê.

Same pattern as rp_contract_inherit.py — adapted cho PO mua hàng.
"""
from odoo import api, fields, models


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    advance_ids = fields.One2many(
        'rp.advance.payment', 'purchase_order_id',
        string='Tạm ứng cho PO này')
    advance_count = fields.Integer(compute='_compute_advance_stats')
    advance_amount_total = fields.Monetary(
        string='Σ tạm ứng',
        compute='_compute_advance_stats', store=True)
    advance_amount_remaining = fields.Monetary(
        string='Tạm ứng chưa cấn trừ',
        compute='_compute_advance_stats', store=True)

    @api.depends('advance_ids.amount', 'advance_ids.amount_remaining',
                 'advance_ids.state')
    def _compute_advance_stats(self):
        for rec in self:
            relevant = rec.advance_ids.filtered(
                lambda a: a.state not in ('draft', 'cancelled'))
            rec.advance_count = len(relevant)
            rec.advance_amount_total = sum(relevant.mapped('amount'))
            paid_or_settled = rec.advance_ids.filtered(
                lambda a: a.state in ('paid', 'settled'))
            rec.advance_amount_remaining = sum(
                paid_or_settled.mapped('amount_remaining'))

    def action_view_advances(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Tạm ứng — %s' % (self.name or ''),
            'res_model': 'rp.advance.payment',
            'view_mode': 'list,form',
            'domain': [('purchase_order_id', '=', self.id)],
            'context': {
                'default_purchase_order_id': self.id,
                'default_partner_id': self.partner_id.id,
            },
        }
