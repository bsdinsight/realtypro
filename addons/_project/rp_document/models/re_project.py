# -*- coding: utf-8 -*-
"""Hồ sơ nhìn từ dự án: bên nào đang giữ bóng.

Một con số duy nhất đáng đưa lên màn hình dự án: **số công việc chưa được
phép khởi công vì hồ sơ**. Nó không nằm trong tiến độ (Gantt vẫn xanh),
không nằm trong chi phí, không ai báo cáo — cho đến lúc trễ thì mới đi
tìm nguyên nhân. Còn lại thì tách rõ bóng đang ở chân ai: hồ sơ nhà thầu
chưa trình, hay hồ sơ bên mình giữ quá hạn.
"""
from odoo import _, api, fields, models


class ReProject(models.Model):
    _inherit = 're.project'

    document_ids = fields.One2many(
        'rp.document', 'project_id', string='Hồ sơ kỹ thuật')
    document_count = fields.Integer(string='Số hồ sơ',
                                    compute='_compute_document_rollup')
    doc_pending_count = fields.Integer(
        string='Hồ sơ đang xem xét', compute='_compute_document_rollup')
    doc_overdue_count = fields.Integer(
        string='Hồ sơ quá hạn xem xét', compute='_compute_document_rollup',
        help='Bên xem xét đang giữ quá hạn 21 ngày của điều 5.2 — mỗi hồ '
             'sơ ở đây là một đơn xin gia hạn đang chờ được viết.')
    doc_not_submitted_count = fields.Integer(
        string='Hồ sơ nhà thầu chưa trình',
        compute='_compute_document_rollup')
    doc_blocked_task_count = fields.Integer(
        string='Việc chưa được phép khởi công',
        compute='_compute_document_rollup',
        help='Công việc có hồ sơ chưa qua điều 5.2. Gantt vẫn báo đúng hạn, '
             'nhưng hợp đồng không cho phép bắt đầu.')
    doc_toc_outstanding_count = fields.Integer(
        string='Hồ sơ còn thiếu để bàn giao',
        compute='_compute_document_rollup')

    @api.depends('document_ids.state', 'document_ids.review_deadline',
                 'document_ids.is_toc_required')
    def _compute_document_rollup(self):
        today = fields.Date.context_today(self)
        Task = self.env['project.task']
        for rec in self:
            docs = rec.document_ids.filtered(
                lambda d: d.state != 'cancelled')
            rec.document_count = len(docs)
            pending = docs.filtered(lambda d: d.state == 'submitted')
            rec.doc_pending_count = len(pending)
            rec.doc_overdue_count = len(pending.filtered(
                lambda d: d.review_deadline and d.review_deadline < today))
            rec.doc_not_submitted_count = len(
                docs.filtered(lambda d: d.state == 'planned'))
            rec.doc_toc_outstanding_count = len(docs.filtered(
                lambda d: d.is_toc_required
                and d.state not in ('approved', 'approved_comment')))
            rec.doc_blocked_task_count = Task.search_count([
                ('rp_project_id', '=', rec.id),
                ('doc_gate_blocked', '=', True),
            ]) if rec.id else 0

    def action_open_documents(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Hồ sơ kỹ thuật — %s', self.name),
            'res_model': 'rp.document',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }

    def action_open_doc_blocked_tasks(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Việc chưa được phép khởi công — %s', self.name),
            'res_model': 'project.task',
            'view_mode': 'list,form',
            'domain': [('rp_project_id', '=', self.id),
                       ('doc_gate_blocked', '=', True)],
            'context': {'search_default_rp_group_contract': 1},
            'search_view_id': [
                self.env.ref('rp_schedule.view_task_search_rp_panel').id,
                'search'],
        }
