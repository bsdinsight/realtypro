# -*- coding: utf-8 -*-
"""Nối rp.contract với sổ bảo lãnh NHẬN từ nhà thầu (O2M + smart button).

Field đặt tên `received_guarantee_*` để KHÔNG đụng `guarantee_ids` của
module rp_guarantee_bridge (nối HĐ với BL NH mình phát hành — chiều
tín dụng, thuộc app Vay). Hai chiều độc lập, cùng tồn tại được.
"""
from odoo import _, api, fields, models


class RpContract(models.Model):
    _inherit = 'rp.contract'

    received_guarantee_ids = fields.One2many(
        'rp.contract.guarantee', 'contract_id',
        string='Bảo lãnh nhận từ nhà thầu')
    received_guarantee_count = fields.Integer(
        compute='_compute_received_guarantee_count')
    received_guarantee_expiring_count = fields.Integer(
        compute='_compute_received_guarantee_count',
        help='Số bảo lãnh nhận đang hiệu lực sắp/đã hết hạn.')

    @api.depends('received_guarantee_ids.state',
                 'received_guarantee_ids.expiry_status')
    def _compute_received_guarantee_count(self):
        for rec in self:
            rec.received_guarantee_count = len(rec.received_guarantee_ids)
            rec.received_guarantee_expiring_count = len(
                rec.received_guarantee_ids.filtered(
                    lambda g: g.state == 'active'
                    and g.expiry_status in ('expiring', 'expired')))

    def action_view_received_guarantees(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'target': 'new',
            'name': _('Bảo lãnh nhận — %s') % self.name,
            'res_model': 'rp.contract.guarantee',
            'view_mode': 'list,form',
            'domain': [('contract_id', '=', self.id)],
            'context': {'default_contract_id': self.id},
        }
