# -*- coding: utf-8 -*-
"""Wizard chấm dứt sớm HĐ thuê — khai lý do / ngày / phạt trước khi
chuyển trạng thái 'Chấm dứt sớm'."""
from odoo import _, fields, models
from odoo.exceptions import UserError


class ReLeaseTerminateWizard(models.TransientModel):
    _name = 're.lease.terminate.wizard'
    _description = 'Wizard chấm dứt sớm HĐ thuê'

    contract_id = fields.Many2one(
        're.lease.contract', string='HĐ thuê', required=True,
        ondelete='cascade')
    currency_id = fields.Many2one(related='contract_id.currency_id')
    termination_date = fields.Date(
        string='Ngày chấm dứt', required=True,
        default=fields.Date.context_today)
    termination_reason = fields.Text(string='Lý do chấm dứt')
    penalty_amount = fields.Monetary(string='Phạt / bồi thường')

    def action_confirm(self):
        self.ensure_one()
        c = self.contract_id
        if c.state not in ('draft', 'active'):
            raise UserError(_('HĐ đã kết thúc.'))
        c._apply_termination(
            self.termination_date, self.termination_reason,
            self.penalty_amount)
        return {'type': 'ir.actions.act_window_close'}
