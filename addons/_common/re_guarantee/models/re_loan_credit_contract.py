# -*- coding: utf-8 -*-
"""Inherit HĐTD: smart button mở list BL + đề nghị BL của HĐTD này."""
from odoo import _, fields, models


class ReLoanCreditContract(models.Model):
    _inherit = 're.loan.credit.contract'

    guarantee_ids = fields.One2many(
        're.bank.guarantee', 'credit_contract_id',
        string='Bảo lãnh NH')
    guarantee_count = fields.Integer(
        compute='_compute_guarantee_count',
        help='Số chứng thư BL gắn với HĐTD qua facility.')

    guarantee_request_ids = fields.One2many(
        're.guarantee.request', 'credit_contract_id',
        string='Đề nghị phát hành BL')
    guarantee_request_count = fields.Integer(
        compute='_compute_guarantee_count')

    def _compute_guarantee_count(self):
        for rec in self:
            rec.guarantee_count = len(rec.guarantee_ids)
            rec.guarantee_request_count = len(rec.guarantee_request_ids)

    def action_view_guarantees(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Bảo lãnh NH — %s") % self.name,
            'res_model': 're.bank.guarantee',
            'view_mode': 'list,kanban,form',
            'domain': [('credit_contract_id', '=', self.id)],
            'context': {
                'default_credit_contract_id': self.id,
            },
        }

    def action_view_guarantee_requests(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Đề nghị BL — %s") % self.name,
            'res_model': 're.guarantee.request',
            'view_mode': 'list,form',
            'domain': [('credit_contract_id', '=', self.id)],
        }
