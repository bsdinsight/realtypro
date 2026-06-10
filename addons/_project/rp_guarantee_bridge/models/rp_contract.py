# -*- coding: utf-8 -*-
"""Inherit HĐ nhà thầu: smart button "Bảo lãnh NH" + tab "Đề nghị BL"."""
from odoo import _, fields, models


class RpContract(models.Model):
    _inherit = 'rp.contract'

    guarantee_ids = fields.One2many(
        're.bank.guarantee', 'rp_contract_id',
        string='Bảo lãnh NH chi tiết')
    guarantee_count = fields.Integer(
        compute='_compute_guarantee_count',
        help='Số BL gắn với HĐ nhà thầu này (chứng thư BL chi tiết, '
             'tách rời 3 nhóm BL inline trên form).')

    guarantee_request_ids = fields.One2many(
        're.guarantee.request', 'rp_contract_id',
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
            'domain': [('rp_contract_id', '=', self.id)],
            'context': {
                'default_rp_contract_id': self.id,
                'default_applicant_partner_id': (
                    self.contractor_id.id if self.contractor_id else False),
            },
        }

    def action_view_guarantee_requests(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Đề nghị BL — %s") % self.name,
            'res_model': 're.guarantee.request',
            'view_mode': 'list,form',
            'domain': [('rp_contract_id', '=', self.id)],
            'context': {
                'default_rp_contract_id': self.id,
                'default_project_id': (
                    self.project_id.id if self.project_id else False),
            },
        }
