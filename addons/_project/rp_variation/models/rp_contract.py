# -*- coding: utf-8 -*-
"""Phát sinh nhìn từ hợp đồng: giá gốc, đã duyệt, đang chờ, dự báo cuối."""
from odoo import _, api, fields, models

APPROVED = ('approved', 'instructed', 'applied')
PENDING = ('draft', 'requested', 'quoted', 'review')


class RpContract(models.Model):
    _inherit = 'rp.contract'

    variation_ids = fields.One2many(
        'rp.variation', 'contract_id', string='Phát sinh')
    variation_count = fields.Integer(
        string='Số phát sinh', compute='_compute_variation_amounts')
    variation_approved_amount = fields.Monetary(
        string='Phát sinh đã duyệt', compute='_compute_variation_amounts',
        store=True)
    variation_pending_amount = fields.Monetary(
        string='Phát sinh đang chờ', compute='_compute_variation_amounts',
        store=True,
        help='Giá nhà thầu đề xuất của các phát sinh chưa duyệt xong — '
             'chưa chắc chắn nhưng phải nhìn thấy khi dự báo chi phí.')
    contract_value_forecast = fields.Monetary(
        string='Giá trị HĐ dự báo', compute='_compute_variation_amounts',
        store=True,
        help='Giá hợp đồng hiện tại cộng phát sinh đã duyệt chưa vào phụ '
             'lục, cộng phát sinh đang chờ.')

    @api.depends('variation_ids.state', 'variation_ids.amount_approved',
                 'variation_ids.amount_quoted', 'contract_value_pretax')
    def _compute_variation_amounts(self):
        for rec in self:
            vs = rec.variation_ids
            rec.variation_count = len(vs)
            # Đã vào phụ lục thì giá hợp đồng đã cộng rồi — không cộng lần
            # thứ hai, nếu không con số dự báo bị đếm đúp.
            approved_open = sum(vs.filtered(
                lambda v: v.state in ('approved', 'instructed')).mapped(
                    'amount_approved'))
            applied = sum(vs.filtered(
                lambda v: v.state == 'applied').mapped('amount_approved'))
            pending = sum(vs.filtered(
                lambda v: v.state in PENDING).mapped('amount_quoted'))
            rec.variation_approved_amount = approved_open + applied
            rec.variation_pending_amount = pending
            rec.contract_value_forecast = (
                rec.contract_value_pretax + approved_open + pending)

    def action_open_variations(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Phát sinh — %s', self.name),
            'res_model': 'rp.variation',
            'view_mode': 'list,form',
            'domain': [('contract_id', '=', self.id)],
            'context': {'default_contract_id': self.id},
        }
