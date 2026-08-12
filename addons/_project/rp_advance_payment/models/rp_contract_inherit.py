# -*- coding: utf-8 -*-
"""Inherit rp.contract: thêm tab Tạm ứng + thống kê."""
from odoo import api, fields, models


class RpContract(models.Model):
    _inherit = 'rp.contract'

    advance_ids = fields.One2many(
        'rp.advance.payment', 'contract_id',
        string='Tạm ứng cho HĐ này')
    advance_count = fields.Integer(compute='_compute_advance_stats')
    advance_amount_total = fields.Monetary(
        string='Σ tạm ứng',
        compute='_compute_advance_stats', store=True)
    advance_amount_remaining = fields.Monetary(
        string='Tạm ứng chưa cấn trừ',
        compute='_compute_advance_stats', store=True,
        help='Tổng các tạm ứng đã thanh toán nhưng chưa cấn trừ đủ '
             'vào hóa đơn (tiềm năng cấn trừ vào hóa đơn tương lai).')

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
            'target': 'new',
            'name': 'Tạm ứng — %s' % (self.name or ''),
            'res_model': 'rp.advance.payment',
            'view_mode': 'list,form',
            'domain': [('contract_id', '=', self.id)],
            'context': {
                'default_contract_id': self.id,
                'default_partner_id': self.contractor_id.id,
            },
        }
