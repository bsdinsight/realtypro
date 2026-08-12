# -*- coding: utf-8 -*-
"""Mở rộng project.task cho lịch thi công xây dựng.

Thêm field xây dựng (HĐ nhà thầu, hạng mục, WBS, ngày KH, %, milestone,
predecessors) — tự khai để không phụ thuộc field native theo phiên bản
Odoo (planned_date_begin/milestone_id là của project_enterprise)."""
from datetime import timedelta

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

    # --- Baseline (kế hoạch gốc đông cứng) — nền để đo SV/SPI ---
    baseline_start = fields.Date(string='Bắt đầu (Baseline)', copy=False)
    baseline_end = fields.Date(string='Kết thúc (Baseline)', copy=False)
    baseline_set_date = fields.Datetime(
        string='Ngày chốt Baseline', copy=False)
    baseline_slip_days = fields.Integer(
        string='Trượt so Baseline (ngày)', compute='_compute_baseline_slip',
        store=True,
        help='Kết thúc KH hiện hành − Kết thúc Baseline. >0 = trễ so gốc.')

    # --- Đường găng (CPM) lưu lại để list/report/KPI dùng ---
    is_critical = fields.Boolean(
        string='Trên đường găng', copy=False, index=True,
        help='Total Float ≤ 0 — chậm ở đây là chậm cả dự án. '
             'Cập nhật bởi "Tính đường găng".')
    total_float = fields.Integer(
        string='Tổng dự trữ (ngày)', copy=False,
        help='LS − ES (backward pass CPM). ≤0 = găng; nhỏ = cận găng.')

    @api.depends('planned_end', 'baseline_end')
    def _compute_baseline_slip(self):
        for t in self:
            if t.planned_end and t.baseline_end:
                t.baseline_slip_days = (t.planned_end - t.baseline_end).days
            else:
                t.baseline_slip_days = 0

    @api.model
    def rp_set_baseline(self, contract_id=None, project_id=None):
        """Chốt baseline: copy ngày kế hoạch hiện hành → baseline cho toàn
        bộ công việc của HĐ (hoặc dự án). Ảnh chụp đông cứng để đo trượt
        tiến độ — re-baseline PHẢI có chủ đích (mục 1 khung phân tích)."""
        domain = [('planned_start', '!=', False),
                  ('planned_end', '!=', False)]
        if contract_id:
            domain.append(('rp_contract_id', '=', int(contract_id)))
        elif project_id:
            domain.append(('rp_contract_id.project_id', '=', int(project_id)))
        tasks = self.search(domain)
        now = fields.Datetime.now()
        for t in tasks:
            t.write({
                'baseline_start': t.planned_start,
                'baseline_end': t.planned_end,
                'baseline_set_date': now,
            })
        return len(tasks)

    @api.model
    def rp_clear_baseline(self, contract_id=None):
        domain = [('baseline_start', '!=', False)]
        if contract_id:
            domain.append(('rp_contract_id', '=', int(contract_id)))
        tasks = self.search(domain)
        tasks.write({'baseline_start': False, 'baseline_end': False,
                     'baseline_set_date': False})
        return len(tasks)

    # --- Đường găng (CPM) — mục 3+11 khung phân tích tiến độ ---
    @api.model
    def rp_compute_critical_path(self, contract_id):
        """Tính Total Float + đường găng cho lịch của 1 HĐ.

        Backward pass trên mạng phụ thuộc FS (predecessor_ids) dùng ngày
        kế hoạch nhập từ MS Project:
          LF(t) = min(LS(succ) − 1) nếu có successor, else ngày kết thúc dự án
          LS(t) = LF(t) − thời lượng
          TF(t) = LS(t) − ES(t)   (ES = ngày bắt đầu KH)
        Găng: TF ≤ 0. Cận găng (near-critical): 0 < TF ≤ 5.
        Trả {task_id: {'tf': int, 'critical': bool, 'near': bool}}.
        Chỉ tính task lá (bỏ WBS tổng). KHÔNG ghi DB — trả trực tiếp cho
        Gantt tô màu, giữ nguyên ngày import.
        """
        cid = int(contract_id)
        tasks = self.search([
            ('rp_contract_id', '=', cid),
            ('planned_start', '!=', False), ('planned_end', '!=', False)])
        if not tasks:
            return {}
        wbs_all = set(t.wbs_code for t in tasks if t.wbs_code)

        def is_summary(t):
            if not t.wbs_code:
                return False
            pre = t.wbs_code + '.'
            return any(w.startswith(pre) for w in wbs_all)

        leaves = [t for t in tasks if not is_summary(t)]
        by_id = {t.id: t for t in leaves}
        succ = {t.id: [] for t in leaves}
        for t in leaves:
            for p in t.predecessor_ids:
                if p.id in by_id:
                    succ[p.id].append(t.id)
        project_end = max(t.planned_end for t in leaves)
        ls_memo, lf_memo, visiting = {}, {}, set()

        def late_start(tid):
            if tid in ls_memo:
                return ls_memo[tid]
            t = by_id[tid]
            dur = (t.planned_end - t.planned_start).days
            ls_memo[tid] = late_finish(tid) - timedelta(days=dur)
            return ls_memo[tid]

        def late_finish(tid):
            if tid in lf_memo:
                return lf_memo[tid]
            if tid in visiting:                      # chặn vòng lặp
                return project_end
            visiting.add(tid)
            ss = succ[tid]
            lf = (project_end if not ss
                  else min(late_start(s) - timedelta(days=1) for s in ss))
            visiting.discard(tid)
            lf_memo[tid] = lf
            return lf

        result = {}
        for t in leaves:
            tf = (late_start(t.id) - t.planned_start).days
            result[t.id] = {
                'tf': tf, 'critical': tf <= 0, 'near': 0 < tf <= 5}
            # Ghi field lưu (chỉ khi đổi) → list/report/KPI dùng được
            if t.total_float != tf or t.is_critical != (tf <= 0):
                t.write({'total_float': tf, 'is_critical': tf <= 0})
        # Task tổng (WBS summary) không nằm trên đường găng
        summary = tasks.filtered(lambda x: x.id not in by_id and x.is_critical)
        if summary:
            summary.write({'is_critical': False, 'total_float': 0})
        return result

    @api.depends('planned_start', 'planned_end')
    def _compute_planned_days(self):
        for t in self:
            if t.planned_start and t.planned_end \
                    and t.planned_end >= t.planned_start:
                t.planned_days = (t.planned_end - t.planned_start).days + 1
            else:
                t.planned_days = 0

    def rp_shift_schedule(self, new_start, new_end):
        """Đổi ngày task + DÂY CHUYỀN dời các task phụ thuộc.

        Gọi từ Gantt khi kéo/resize bar:
        - Task này nhận ngày mới.
        - Kéo cả thanh (delta start == delta end) và task có con →
          cả CÂY CON dời theo cùng delta (dời giai đoạn = dời mọi việc
          bên trong).
        - Các task ĐỨNG SAU (successor theo predecessor_ids, cùng HĐ)
          dời theo delta của NGÀY KẾT THÚC, lan truyền đến hết chuỗi —
          giữ nguyên khoảng lag tương đối giữa các task như MS Project.
        - Xong cuộn lại ngày các task cha (summary).

        Trả về list id các task đã đổi ngày (Gantt reload khi > 1).
        """
        self.ensure_one()
        old_start = self.planned_start
        old_end = self.planned_end or self.planned_start
        ns = fields.Date.from_string(new_start) if new_start else False
        ne = fields.Date.from_string(new_end) if new_end else ns
        self.write({'planned_start': ns, 'planned_end': ne})
        changed = {self.id}
        d_start = (ns - old_start).days if (ns and old_start) else 0
        d_end = (ne - old_end).days if (ne and old_end) else 0

        def shift(task, days):
            vals = {}
            if task.planned_start:
                vals['planned_start'] = \
                    task.planned_start + timedelta(days=days)
            if task.planned_end:
                vals['planned_end'] = \
                    task.planned_end + timedelta(days=days)
            if vals:
                task.write(vals)
                changed.add(task.id)

        # 1) Kéo cả thanh của task CHA → cây con dời cùng delta
        if d_start and d_start == d_end and self.child_ids:
            subtree = self.search([
                ('id', 'child_of', self.id), ('id', '!=', self.id)])
            for t in subtree:
                shift(t, d_start)

        # 2) Dây chuyền successor theo delta ngày kết thúc (BFS, chặn
        #    vòng lặp bằng visited = changed)
        if d_end and self.rp_contract_id:
            frontier = list(changed)
            while frontier:
                succs = self.search([
                    ('predecessor_ids', 'in', frontier),
                    ('rp_contract_id', '=', self.rp_contract_id.id),
                    ('id', 'not in', list(changed)),
                ])
                frontier = []
                for s in succs:
                    shift(s, d_end)
                    frontier.append(s.id)

        # 3) Cuộn lại ngày cha (summary) theo con — cha nào bị đổi do
        #    rollup cũng đưa vào changed để Gantt reload đủ
        if self.rp_contract_id:
            before = {
                t.id: (t.planned_start, t.planned_end)
                for t in self.rp_contract_id.task_ids}
            self.rp_contract_id._rollup_schedule_parent_dates()
            for t in self.rp_contract_id.task_ids:
                if before.get(t.id) != (t.planned_start, t.planned_end):
                    changed.add(t.id)
        return sorted(changed)

    def write(self, vals):
        """Đổi % (từ Gantt, form, list...) → tự cuộn % lên chuỗi cha.

        % cha = bình quân trọng số theo số ngày KH của các con (bỏ
        milestone). Context `rp_skip_progress_rollup` chặn đệ quy khi
        chính rollup ghi % cho cha.
        """
        res = super().write(vals)
        if 'progress_percent' in vals \
                and not self.env.context.get('rp_skip_progress_rollup'):
            parents = self.mapped('parent_id')
            seen = set()
            while parents:
                nxt = self.env['project.task']
                for p in parents:
                    if p.id in seen:
                        continue
                    seen.add(p.id)
                    kids = p.child_ids.filtered(
                        lambda t: not t.is_milestone)
                    if kids:
                        total_w = sum(kids.mapped('planned_days'))
                        if total_w:
                            pct = sum(
                                k.progress_percent * k.planned_days
                                for k in kids) / total_w
                        else:
                            pct = sum(kids.mapped(
                                'progress_percent')) / len(kids)
                        p.with_context(
                            rp_skip_progress_rollup=True,
                        ).write({'progress_percent': round(pct, 1)})
                    if p.parent_id:
                        nxt |= p.parent_id
                parents = nxt
        return res

    def rp_update_progress(self, value):
        """Cập nhật % từ Gantt — rollup cha do write() lo.

        Trả về [id + chuỗi cha] để Gantt biết reload.
        """
        self.ensure_one()
        value = max(0.0, min(100.0, value or 0.0))
        self.write({'progress_percent': value})
        changed = [self.id]
        parent = self.parent_id
        while parent:
            changed.append(parent.id)
            parent = parent.parent_id
        return changed

    @api.constrains('progress_percent')
    def _check_progress(self):
        from odoo.exceptions import ValidationError
        from odoo import _
        for t in self:
            if t.progress_percent < 0 or t.progress_percent > 100:
                raise ValidationError(_(
                    '% hoàn thành phải trong khoảng 0–100.'))
