# -*- coding: utf-8 -*-
"""HĐ nhà thầu: smart button RFI mở / chỉ thị chưa xong / trình duyệt chờ."""
from odoo import _, fields, models


class RpContract(models.Model):
    _inherit = 'rp.contract'

    open_rfi_count = fields.Integer(compute='_compute_rfi_counts')
    open_instruction_count = fields.Integer(compute='_compute_rfi_counts')
    pending_submittal_count = fields.Integer(compute='_compute_rfi_counts')

    def _compute_rfi_counts(self):
        Rfi = self.env['rp.rfi']
        Si = self.env['rp.site.instruction']
        Sub = self.env['rp.submittal']
        for c in self:
            c.open_rfi_count = Rfi.search_count(
                [('contract_id', '=', c.id),
                 ('state', 'in', ('submitted', 'answered'))])
            c.open_instruction_count = Si.search_count(
                [('contract_id', '=', c.id),
                 ('state', 'in', ('issued', 'done'))])
            c.pending_submittal_count = Sub.search_count(
                [('contract_id', '=', c.id),
                 ('state', 'in', ('submitted', 'rejected'))])

    def _open_site_docs(self, model, name, extra_ctx=None):
        self.ensure_one()
        ctx = {'default_contract_id': self.id,
               'default_project_id': self.project_id.id}
        ctx.update(extra_ctx or {})
        return {
            'type': 'ir.actions.act_window',
            'name': _('%s — %s', name, self.name),
            'res_model': model,
            'view_mode': 'list,form',
            'domain': [('contract_id', '=', self.id)],
            'context': ctx,
        }

    def action_view_rfis(self):
        return self._open_site_docs('rp.rfi', _('RFI'))

    def action_view_instructions(self):
        return self._open_site_docs(
            'rp.site.instruction', _('Chỉ thị công trường'))

    def action_view_submittals(self):
        return self._open_site_docs('rp.submittal', _('Trình duyệt'))
