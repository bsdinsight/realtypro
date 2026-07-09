# -*- coding: utf-8 -*-
"""HĐ nhà thầu: gắn 1 project.project (lịch thi công) + rollup % theo lịch."""
from odoo import _, api, fields, models


class RpContract(models.Model):
    _inherit = 'rp.contract'

    schedule_project_id = fields.Many2one(
        'project.project', string='Dự án công việc (lịch thi công)',
        copy=False, ondelete='set null')
    task_ids = fields.One2many(
        'project.task', 'rp_contract_id', string='Công việc')
    task_count = fields.Integer(compute='_compute_schedule')
    schedule_progress = fields.Float(
        string='% tiến độ (theo lịch)', compute='_compute_schedule',
        store=True,
        help='Trung bình % hoàn thành các công việc, trọng số theo số '
             'ngày kế hoạch (bỏ qua milestone).')

    @api.depends('task_ids.progress_percent', 'task_ids.planned_days',
                 'task_ids.is_milestone')
    def _compute_schedule(self):
        for c in self:
            tasks = c.task_ids.filtered(lambda t: not t.is_milestone)
            c.task_count = len(c.task_ids)
            total_w = sum(tasks.mapped('planned_days')) or 0
            if total_w:
                c.schedule_progress = sum(
                    t.progress_percent * t.planned_days for t in tasks
                ) / total_w
            elif tasks:
                c.schedule_progress = sum(
                    tasks.mapped('progress_percent')) / len(tasks)
            else:
                c.schedule_progress = 0.0

    def _get_or_create_schedule_project(self):
        self.ensure_one()
        if not self.schedule_project_id:
            self.schedule_project_id = self.env['project.project'].create({
                'name': _('%s — Lịch thi công', self.name or self.id),
                'company_id': self.company_id.id,
            })
        return self.schedule_project_id

    def action_open_schedule(self):
        self.ensure_one()
        proj = self._get_or_create_schedule_project()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Lịch thi công — %s', self.name),
            'res_model': 'project.task',
            'view_mode': 'list,form',
            'domain': [('rp_contract_id', '=', self.id)],
            'context': {
                'default_rp_contract_id': self.id,
                'default_project_id': proj.id,
            },
        }

    def action_import_schedule(self):
        self.ensure_one()
        self._get_or_create_schedule_project()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Import lịch thi công — %s', self.name),
            'res_model': 'rp.schedule.import.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_contract_id': self.id},
        }
