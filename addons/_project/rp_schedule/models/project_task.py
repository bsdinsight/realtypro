# -*- coding: utf-8 -*-
"""Mở rộng project.task cho lịch thi công xây dựng.

Thêm field xây dựng (HĐ nhà thầu, hạng mục, WBS, ngày KH, %, milestone,
predecessors) — tự khai để không phụ thuộc field native theo phiên bản
Odoo (planned_date_begin/milestone_id là của project_enterprise)."""
from odoo import api, fields, models


class ProjectTask(models.Model):
    _inherit = 'project.task'

    rp_contract_id = fields.Many2one(
        'rp.contract', string='HĐ nhà thầu', index=True, ondelete='cascade')
    rp_structure_id = fields.Many2one(
        'rp.structure', string='Hạng mục (đầu việc)', index=True)
    wbs_code = fields.Char(string='Mã WBS', index=True)
    planned_start = fields.Date(string='Bắt đầu (KH)')
    planned_end = fields.Date(string='Kết thúc (KH)')
    planned_days = fields.Integer(
        string='Số ngày KH', compute='_compute_planned_days', store=True)
    progress_percent = fields.Float(string='% hoàn thành', default=0.0)
    is_milestone = fields.Boolean(string='Là mốc (milestone)')
    predecessor_ids = fields.Many2many(
        'project.task', 'rp_task_predecessor_rel', 'task_id', 'pred_id',
        string='Công việc trước')
    external_uid = fields.Char(
        string='UID nguồn (MPP/Excel)', index=True, copy=False,
        help='Định danh task từ file nguồn — dùng để re-import idempotent.')

    @api.depends('planned_start', 'planned_end')
    def _compute_planned_days(self):
        for t in self:
            if t.planned_start and t.planned_end \
                    and t.planned_end >= t.planned_start:
                t.planned_days = (t.planned_end - t.planned_start).days + 1
            else:
                t.planned_days = 0

    @api.constrains('progress_percent')
    def _check_progress(self):
        from odoo.exceptions import ValidationError
        from odoo import _
        for t in self:
            if t.progress_percent < 0 or t.progress_percent > 100:
                raise ValidationError(_(
                    '% hoàn thành phải trong khoảng 0–100.'))
