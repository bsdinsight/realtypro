# -*- coding: utf-8 -*-
"""Inherit rp.tender.package — thêm O2M contracts + smart button."""
from odoo import api, fields, models


class RpTenderPackage(models.Model):
    _inherit = 'rp.tender.package'

    contract_ids = fields.One2many(
        'rp.contract', 'tender_package_id', string='Hợp đồng nhà thầu')
    contract_count = fields.Integer(
        string='Số HĐ', compute='_compute_contract_count')
    contract_value_signed = fields.Monetary(
        string='Tổng giá trị HĐ đã ký', compute='_compute_contract_stats',
        store=True)

    @api.depends('contract_ids')
    def _compute_contract_count(self):
        for rec in self:
            rec.contract_count = len(rec.contract_ids)

    @api.depends('contract_ids.state',
                 'contract_ids.contract_value_total')
    def _compute_contract_stats(self):
        for rec in self:
            rec.contract_value_signed = sum(rec.contract_ids.filtered(
                lambda c: c.state in ('signed', 'executing', 'completed')
            ).mapped('contract_value_total'))

    def action_view_contracts(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Hợp đồng nhà thầu',
            'res_model': 'rp.contract',
            'view_mode': 'list,form',
            'domain': [('tender_package_id', '=', self.id)],
            'context': {
                'default_tender_package_id': self.id,
                'default_contractor_id':
                    self.contractor_id.id if self.contractor_id else False,
            },
        }
