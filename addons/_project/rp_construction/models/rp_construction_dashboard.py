# -*- coding: utf-8 -*-
"""Dashboard Xây dựng — KPI thi công hiện trường + drill-down.

Pattern giống rp_dashboard/rp_finance: TransientModel, default_get()
query realtime. Nhấp menu "Xây dựng" → menu con seq nhỏ nhất là
Dashboard nên dashboard mở ngay.
"""
from odoo import api, fields, models


class RpConstructionDashboard(models.TransientModel):
    _name = 'rp.construction.dashboard'
    _description = 'Realty Project — Dashboard Xây dựng'

    @api.depends_context('lang')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = 'Xây dựng — Dashboard'

    # ─── 1. Tiến độ thi công ──────────────────────────────────────
    kpi_task_active = fields.Integer(
        string='Công việc đang thi công',
        help='Task lịch thi công đang trong khoảng ngày kế hoạch, '
             'chưa xong 100%.')
    kpi_task_overdue = fields.Integer(
        string='Công việc trễ hạn',
        help='Task quá ngày kết thúc kế hoạch mà % < 100. Highlight ĐỎ.')
    kpi_acceptance_pending = fields.Integer(
        string='BBN chờ CĐT duyệt',
        help='BBN Nghiệm thu KL state = proposed.')

    # ─── 2. Hiện trường ───────────────────────────────────────────
    kpi_punch_open = fields.Integer(
        string='Punch đang mở',
        help='Lỗi state ∈ {open, in_progress}.')
    kpi_punch_overdue = fields.Integer(
        string='Punch quá hạn',
        help='Lỗi đang mở đã quá hạn khắc phục. Highlight ĐỎ.')
    kpi_diary_pending = fields.Integer(
        string='Nhật ký chờ xác nhận',
        help='Nhật ký thi công state = submitted.')
    kpi_incident_30d = fields.Integer(
        string='Sự cố/near-miss 30 ngày',
        help='Sự cố an toàn ghi nhận trong 30 ngày gần nhất.')

    # ─── 3. RFI & phê duyệt ───────────────────────────────────────
    kpi_rfi_waiting = fields.Integer(
        string='RFI chờ trả lời',
        help='RFI state = submitted.')
    kpi_rfi_overdue = fields.Integer(
        string='RFI trễ hạn trả lời',
        help='RFI chờ trả lời đã quá hạn — căn cứ claim tiến độ. '
             'Highlight ĐỎ.')
    kpi_instruction_open = fields.Integer(
        string='Chỉ thị chưa thực hiện',
        help='Chỉ thị công trường state = issued.')
    kpi_submittal_pending = fields.Integer(
        string='Submittal chờ duyệt',
        help='Trình duyệt vật liệu/shopdrawing state = submitted.')
    project_id = fields.Many2one(
        're.project', string='Lọc theo dự án',
        help='Bỏ trống = tổng hợp tất cả dự án.')

    # ------------------------------------------------------------------
    # Compute
    # ------------------------------------------------------------------
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        res.update(self._compute_kpis())
        return res

    @api.onchange('project_id')
    def _onchange_project_id(self):
        self.update(self._compute_kpis(self.project_id.id))

    def _compute_kpis(self, project_id=False):
        pid = project_id
        pf = [('project_id', '=', pid)] if pid else []           # có project_id
        pt = [('rp_contract_id.project_id', '=', pid)] if pid else []  # task qua HĐ
        Task = self.env['project.task']
        Punch = self.env['rp.site.punch']
        Rfi = self.env['rp.rfi']
        today = fields.Date.context_today(self)

        open_punch = Punch.search(
            [('state', 'in', ('open', 'in_progress'))] + pf)
        waiting_rfi = Rfi.search([('state', '=', 'submitted')] + pf)

        return {
            'kpi_task_active': Task.search_count([
                ('rp_contract_id', '!=', False),
                ('is_milestone', '=', False),
                ('planned_start', '<=', today),
                ('planned_end', '>=', today),
                ('progress_percent', '<', 100)] + pt),
            'kpi_task_overdue': Task.search_count([
                ('rp_contract_id', '!=', False),
                ('is_milestone', '=', False),
                ('planned_end', '<', today),
                ('progress_percent', '<', 100)] + pt),
            'kpi_acceptance_pending': self.env[
                'rp.progress.acceptance'].search_count(
                [('state', '=', 'proposed')] + pf),
            'kpi_punch_open': len(open_punch),
            # is_overdue compute không store → filtered
            'kpi_punch_overdue': len(open_punch.filtered('is_overdue')),
            'kpi_diary_pending': self.env['rp.site.diary'].search_count(
                [('state', '=', 'submitted')] + pf),
            'kpi_incident_30d': self.env['rp.site.incident'].search_count(
                [('date', '>=', fields.Datetime.subtract(
                    fields.Datetime.now(), days=30))] + pf),
            'kpi_rfi_waiting': len(waiting_rfi),
            'kpi_rfi_overdue': len(waiting_rfi.filtered('is_overdue')),
            'kpi_instruction_open': self.env[
                'rp.site.instruction'].search_count(
                [('state', '=', 'issued')] + pf),
            'kpi_submittal_pending': self.env['rp.submittal'].search_count(
                [('state', '=', 'submitted')] + pf),
        }

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_refresh(self):
        self.write(self._compute_kpis(self.project_id.id))
        return True

    def _open(self, name, res_model, domain=None, context=None):
        return {
            'type': 'ir.actions.act_window',
            'name': name,
            'res_model': res_model,
            'view_mode': 'list,form',
            'domain': domain or [],
            'context': context or {},
            'target': 'current',
        }

    @property
    def _pf(self):
        return [('project_id', '=', self.project_id.id)] if self.project_id else []

    def action_open_tasks_overdue(self):
        today = fields.Date.context_today(self)
        pt = [('rp_contract_id.project_id', '=', self.project_id.id)] \
            if self.project_id else []
        return self._open(
            'Công việc trễ hạn', 'project.task',
            [('rp_contract_id', '!=', False), ('is_milestone', '=', False),
             ('planned_end', '<', today), ('progress_percent', '<', 100)] + pt)

    def action_open_acceptances(self):
        return self._open(
            'BBN chờ duyệt', 'rp.progress.acceptance',
            [('state', '=', 'proposed')] + self._pf)

    def action_open_punches(self):
        return self._open(
            'Punch đang mở', 'rp.site.punch',
            [('state', 'in', ('open', 'in_progress'))] + self._pf)

    def action_open_diaries(self):
        return self._open(
            'Nhật ký chờ xác nhận', 'rp.site.diary',
            [('state', '=', 'submitted')] + self._pf)

    def action_open_incidents(self):
        return self._open(
            'Sự cố 30 ngày', 'rp.site.incident',
            [('date', '>=', fields.Datetime.subtract(
                fields.Datetime.now(), days=30))] + self._pf)

    def action_open_rfis(self):
        return self._open(
            'RFI chờ trả lời', 'rp.rfi',
            [('state', '=', 'submitted')] + self._pf)

    def action_open_instructions(self):
        return self._open(
            'Chỉ thị chưa thực hiện', 'rp.site.instruction',
            [('state', '=', 'issued')] + self._pf)

    def action_open_submittals(self):
        return self._open(
            'Submittal chờ duyệt', 'rp.submittal',
            [('state', '=', 'submitted')] + self._pf)
