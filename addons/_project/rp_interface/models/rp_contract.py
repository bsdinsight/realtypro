# -*- coding: utf-8 -*-
"""Ranh giới nhìn từ một gói thầu: mình nợ ai, và chờ ai."""
from odoo import _, api, fields, models


class RpContract(models.Model):
    _inherit = 'rp.contract'

    interface_out_ids = fields.One2many(
        'rp.interface', 'from_contract_id', string='Phải bàn giao cho')
    interface_in_ids = fields.One2many(
        'rp.interface', 'to_contract_id', string='Chờ nhận từ')
    interface_out_count = fields.Integer(
        string='Số điểm phải giao', compute='_compute_interface_counts')
    interface_in_count = fields.Integer(
        string='Số điểm phải nhận', compute='_compute_interface_counts')

    @api.depends('interface_out_ids.state', 'interface_in_ids.state')
    def _compute_interface_counts(self):
        for rec in self:
            rec.interface_out_count = len(rec.interface_out_ids.filtered(
                lambda i: i.state not in ('closed', 'cancelled')))
            rec.interface_in_count = len(rec.interface_in_ids.filtered(
                lambda i: i.state not in ('closed', 'cancelled')))

    def _action_interfaces(self, field):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Điểm bàn giao — %s', self.name),
            'res_model': 'rp.interface',
            'view_mode': 'list,form',
            'domain': [(field, '=', self.id)],
            'context': {'default_%s' % field: self.id,
                        'default_project_id': self.project_id.id},
        }

    def action_open_interfaces_out(self):
        return self._action_interfaces('from_contract_id')

    def action_open_interfaces_in(self):
        return self._action_interfaces('to_contract_id')
