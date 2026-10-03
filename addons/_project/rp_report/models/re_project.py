# -*- coding: utf-8 -*-
"""Nút chốt số kỳ báo cáo ngay trên form dự án."""
from odoo import _, fields, models


class ReProject(models.Model):
    _inherit = 're.project'

    brief_ids = fields.One2many(
        'rp.project.brief', 'project_id', string='Bản tổng hợp theo kỳ')

    def action_capture_brief(self):
        """Chốt số kỳ này — dùng trước cuộc họp giao ban."""
        self.ensure_one()
        brief = self.env['rp.project.brief']._capture(self)
        return {
            'type': 'ir.actions.act_window',
            'name': _('Bản tổng hợp — %s', self.name),
            'res_model': 'rp.project.brief',
            'res_id': brief.id,
            'views': [[False, 'form']],
        }

    def action_open_briefs(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Bản tổng hợp theo kỳ — %s', self.name),
            'res_model': 'rp.project.brief',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }
