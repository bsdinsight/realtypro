# -*- coding: utf-8 -*-
"""Bridge: weighted progress của dự án từ structures."""
from odoo import api, fields, models


class ReProject(models.Model):
    _inherit = 're.project'

    structure_ids = fields.One2many(
        'rp.structure', 'project_id', string='Hạng mục công trình')

    weighted_progress_percent = fields.Float(
        string='% hoàn thành tổng dự án',
        compute='_compute_weighted_progress', store=True,
        help='Trọng số theo giá trị dự toán: '
             'Σ(structure.progress × structure.estimate_value) / '
             'Σ(structure.estimate_value).')
    delayed_structure_count = fields.Integer(
        string='Số hạng mục chậm',
        compute='_compute_weighted_progress', store=True)
    completed_structure_count = fields.Integer(
        string='Số hạng mục đã hoàn thành',
        compute='_compute_weighted_progress', store=True)
    project_status = fields.Selection(
        [('on_track', 'Đúng tiến độ'),
         ('at_risk', 'Có rủi ro'),
         ('behind', 'Chậm tiến độ'),
         ('critical', 'Nguy cấp')],
        string='Trạng thái tiến độ',
        compute='_compute_project_status', store=True)

    @api.depends('structure_ids', 'structure_ids.progress_percent',
                 'structure_ids.estimate_value',
                 'structure_ids.is_delayed',
                 'structure_ids.status')
    def _compute_weighted_progress(self):
        for rec in self:
            structures = rec.structure_ids
            total_weight = sum(structures.mapped('estimate_value'))
            if total_weight:
                weighted = sum(
                    s.progress_percent * s.estimate_value
                    for s in structures)
                rec.weighted_progress_percent = weighted / total_weight
            else:
                # CHƯA có dự toán ở hạng mục nào → KHÔNG lấy trung bình
                # cộng %HT các hạng mục: nó cho ra con số không ăn khớp
                # EV/BAC (từng hiện 105,82% trong khi giá trị làm ra mới
                # ~1% ngân sách). Chưa có trọng số thì trả 0 cho trung
                # thực — anh Đại chốt 2026-08-11.
                rec.weighted_progress_percent = 0.0
            rec.delayed_structure_count = len(structures.filtered('is_delayed'))
            rec.completed_structure_count = len(
                structures.filtered(lambda s: s.status == 'completed'))

    @api.depends('delayed_structure_count', 'weighted_progress_percent')
    def _compute_project_status(self):
        for rec in self:
            n_delayed = rec.delayed_structure_count
            if n_delayed == 0:
                rec.project_status = 'on_track'
            elif n_delayed <= 2:
                rec.project_status = 'at_risk'
            elif n_delayed <= 5:
                rec.project_status = 'behind'
            else:
                rec.project_status = 'critical'

    # ------------------------------------------------------------------
    # BBNT nghiệm thu — quick-access từ project form
    # ------------------------------------------------------------------
    acceptance_ids = fields.One2many(
        'rp.progress.acceptance', 'project_id',
        string='BBNT nghiệm thu của dự án')
    acceptance_count = fields.Integer(compute='_compute_acceptance_count')

    @api.depends('acceptance_ids')
    def _compute_acceptance_count(self):
        for rec in self:
            rec.acceptance_count = len(rec.acceptance_ids)

    def action_view_acceptances(self):
        self.ensure_one()
        return {
            'name': 'BBNT nghiệm thu — %s' % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'rp.progress.acceptance',
            'view_mode': 'list,kanban,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'search_default_g_contract': 1},
        }

    def action_open_gantt(self):
        """Mở client action BSDGanttView với context dự án này.

        Community: dùng FrappeGanttAdapter (cap 500 hạng mục).
        Enterprise: override service 'bsd_gantt_adapter' để inject
        BryntumGanttAdapter (unlimited + critical path + baseline).
        """
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'bsd_gantt_view',
            'name': 'Gantt — %s' % self.name,
            'context': {'default_project_id': self.id,
                        'active_id': self.id},
        }

    def action_view_structures(self):
        self.ensure_one()
        return {
            'name': 'Hạng mục — %s' % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'rp.structure',
            'view_mode': 'kanban,list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }
