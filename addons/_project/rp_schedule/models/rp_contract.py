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

    # --- Phân tích tiến độ: baseline + đường găng (mục 1+3 khung) ---
    critical_task_count = fields.Integer(
        string='Công việc trên đường găng',
        compute='_compute_schedule_analysis')
    near_critical_count = fields.Integer(
        string='Cận găng (dự trữ ≤ 5 ngày)',
        compute='_compute_schedule_analysis')
    critical_pct = fields.Float(
        string='% công việc găng', compute='_compute_schedule_analysis')
    baseline_slip_max = fields.Integer(
        string='Trượt baseline lớn nhất (ngày)',
        compute='_compute_schedule_analysis')
    has_baseline = fields.Boolean(
        string='Đã chốt baseline', compute='_compute_schedule_analysis')

    def _compute_schedule_analysis(self):
        Task = self.env['project.task']
        for c in self:
            tasks = Task.search([
                ('rp_contract_id', '=', c.id),
                ('planned_start', '!=', False)])
            crit = tasks.filtered('is_critical')
            near = tasks.filtered(lambda t: 0 < t.total_float <= 5)
            base = tasks.filtered('baseline_end')
            c.critical_task_count = len(crit)
            c.near_critical_count = len(near)
            c.critical_pct = (len(crit) / len(tasks) * 100.0) if tasks else 0.0
            c.baseline_slip_max = max(
                base.mapped('baseline_slip_days'), default=0)
            c.has_baseline = bool(base)

    def action_recompute_critical_path(self):
        """Tính lại đường găng + total float, ghi vào công việc."""
        self.ensure_one()
        self.env['project.task'].rp_compute_critical_path(self.id)
        return {
            'type': 'ir.actions.client', 'tag': 'reload',
        }

    def action_set_schedule_baseline(self):
        """Chốt baseline = copy lịch KH hiện hành làm mốc gốc."""
        self.ensure_one()
        self.env['project.task'].rp_set_baseline(contract_id=self.id)
        return {'type': 'ir.actions.client', 'tag': 'reload'}

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

    def _relink_schedule_hierarchy(self):
        """Nối parent_id các công việc theo mã WBS.

        "1.2" là con của "1"; cấp 1 ("1", "2"...) là con của dòng tổng
        "0" nếu có. Nhờ đó tab Sub-tasks trên form task phản ánh đúng
        cây WBS (Gantt suy cây từ WBS độc lập, không phụ thuộc field này).
        """
        for c in self:
            tasks = c.task_ids.filtered('wbs_code')
            by_wbs = {t.wbs_code.strip(): t for t in tasks}
            for t in tasks:
                w = t.wbs_code.strip()
                if '.' in w:
                    parent = by_wbs.get(w.rsplit('.', 1)[0])
                else:
                    parent = by_wbs.get('0') if w != '0' else False
                pid = parent.id if parent and parent is not t else False
                if (t.parent_id.id or False) != pid:
                    t.parent_id = pid

    def _rollup_schedule_parent_dates(self):
        """Cuộn ngày KH của task CHA = min/max các con (kiểu MS Project).

        Dòng summary trong file import thường mang ngày rác/lệch con;
        chuẩn MS Project là ngày summary suy từ con. Đi từ sâu lên nông
        để cha cấp trên nhận ngày đã cuộn của cha cấp dưới.
        """
        for c in self:
            tasks = c.task_ids.filtered('wbs_code')
            kids = {}
            for t in tasks:
                if t.parent_id and t.parent_id in tasks:
                    kids.setdefault(t.parent_id.id, []).append(t)
            for t in sorted(tasks,
                            key=lambda x: x.wbs_code.count('.'),
                            reverse=True):
                ch = kids.get(t.id)
                if not ch:
                    continue
                starts = [x.planned_start for x in ch if x.planned_start]
                ends = [x.planned_end for x in ch if x.planned_end]
                vals = {}
                if starts and t.planned_start != min(starts):
                    vals['planned_start'] = min(starts)
                if ends and t.planned_end != max(ends):
                    vals['planned_end'] = max(ends)
                if vals:
                    t.write(vals)

    def action_open_schedule(self):
        self.ensure_one()
        proj = self._get_or_create_schedule_project()
        return {
            'type': 'ir.actions.act_window',
            'target': 'new',
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

    def action_open_gantt(self):
        """Mở Gantt (frappe-gantt) cho lịch thi công của HĐ này."""
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'rp_schedule.gantt',
            'name': _('Gantt — %s', self.name),
            'context': {'default_rp_contract_id': self.id, 'active_id': self.id},
        }
