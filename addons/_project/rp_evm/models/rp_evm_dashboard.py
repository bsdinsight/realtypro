# -*- coding: utf-8 -*-
"""Dashboard EVM cấp dự án cho Ban QLDA — KPI + CPI theo hạng mục (đèn
giao thông) + so sánh BAC/EV/AC/EAC + S-curve PV/EV/AC, render SVG
server-side.

Ngoài form-view cũ (rollup re.project), module bổ sung **client action**
``rp_evm.dashboard`` (OWL + Syncfusion) — bảng điều khiển dự án trực quan:
S-curve PV/EV/AC time-phased, KPI CPI/SPI, tiến độ theo gói thầu, dòng
tiền thu/chi. Toàn bộ số liệu tính trực tiếp từ chứng từ nguồn
(HĐ thầu phụ = BAC · BBN nghiệm thu = EV · hóa đơn nhà thầu = AC ·
lịch thi công = PV) để nhất quán, không phụ thuộc rollup.
"""
from collections import defaultdict
from datetime import date, timedelta

from odoo import api, fields, models

from . import evm_svg
from .rp_structure import planned_fraction


class RpEvmDashboard(models.TransientModel):
    _name = 'rp.evm.dashboard'
    _description = 'EVM — Dashboard kiểm soát chi phí'

    project_id = fields.Many2one(
        're.project', string='Dự án', required=True,
        default=lambda self: self.env['re.project'].search([], limit=1))
    currency_id = fields.Many2one(
        related='project_id.currency_id', readonly=True)

    # --- KPI (từ rollup re.project) ---
    kpi_bac = fields.Monetary(string='Ngân sách (BAC)',
                              compute='_compute_dashboard')
    kpi_ev = fields.Monetary(string='Giá trị làm ra (EV)',
                             compute='_compute_dashboard')
    kpi_ac = fields.Monetary(string='Chi phí thực (AC)',
                             compute='_compute_dashboard')
    kpi_cv = fields.Monetary(string='Chênh chi phí (CV)',
                             compute='_compute_dashboard')
    kpi_cpi = fields.Float(string='CPI dự án', digits=(16, 2),
                           compute='_compute_dashboard')
    kpi_eac = fields.Monetary(string='Dự báo chi cuối (EAC)',
                              compute='_compute_dashboard')
    kpi_vac = fields.Monetary(string='Chênh khi hoàn thành (VAC)',
                              compute='_compute_dashboard')
    kpi_progress = fields.Float(string='% hoàn thành (EV/BAC)',
                                compute='_compute_dashboard')
    kpi_pv_today = fields.Monetary(string='Kế hoạch đến nay — PV(t)',
                                   compute='_compute_dashboard')
    kpi_spi = fields.Float(string='SPI dự án', digits=(16, 2),
                           compute='_compute_dashboard')
    kpi_sv = fields.Monetary(string='Chênh tiến độ (SV)',
                             compute='_compute_dashboard')
    kpi_over_count = fields.Integer(string='Hạng mục vượt chi',
                                    compute='_compute_dashboard')
    cost_status = fields.Selection(
        [('no_data', 'Chưa đủ dữ liệu'),
         ('on_budget', 'Trong ngân sách'),
         ('watch', 'Cần theo dõi'),
         ('over', 'Vượt chi')],
        string='Trạng thái chi phí', compute='_compute_dashboard')

    # --- Charts SVG ---
    chart_cpi_html = fields.Html(
        string='CPI theo hạng mục', compute='_compute_dashboard',
        sanitize=False)
    chart_cost_html = fields.Html(
        string='So sánh BAC / EV / AC / EAC', compute='_compute_dashboard',
        sanitize=False)
    chart_scurve_html = fields.Html(
        string='S-curve PV / EV / AC', compute='_compute_dashboard',
        sanitize=False)

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = 'EVM — Kiểm soát chi phí'

    @api.depends('project_id')
    def _compute_dashboard(self):
        for d in self:
            p = d.project_id
            d.kpi_bac = p.total_bac
            d.kpi_ev = p.total_ev
            d.kpi_ac = p.total_ac
            d.kpi_cv = p.total_cv
            d.kpi_cpi = p.project_cpi
            d.kpi_eac = p.project_eac
            d.kpi_vac = p.project_vac
            d.kpi_over_count = p.over_budget_count
            d.cost_status = p.cost_status or 'no_data'
            d.kpi_progress = (
                (p.total_ev / p.total_bac * 100.0) if p.total_bac else 0.0)
            # CPI theo hạng mục — chỉ hạng mục có dữ liệu, xếp CPI tăng dần
            # (vượt chi nặng nhất lên đầu)
            structs = p.structure_ids.filtered(
                lambda s: s.estimate_value or s.actual_cost)
            structs = structs.sorted(
                key=lambda s: (s.cpi if s.cpi else 999.0))
            rows = [(s.display_name, s.cpi, s.cost_status) for s in structs]
            d.chart_cpi_html = evm_svg.cpi_bars(rows)
            d.chart_cost_html = evm_svg.cost_compare(
                p.total_bac, p.total_ev, p.total_ac, p.project_eac)
            # Schedule (Phase 4)
            d.kpi_pv_today = p.total_pv_today
            d.kpi_spi = p.project_spi
            d.kpi_sv = p.total_sv
            d.chart_scurve_html = self._build_scurve(p)

    def _build_scurve(self, p, samples=40):
        """S-curve PV tích lũy toàn dự án (Σ BAC×f(t) mọi hạng mục) +
        điểm EV/AC hôm nay."""
        today = fields.Date.context_today(self)
        planned = p.structure_ids.filtered(
            lambda s: s.date_planned_start and s.date_planned_end
            and s.estimate_value)
        if not planned:
            return evm_svg.s_curve([], 0, 0, 0)
        start = min(planned.mapped('date_planned_start'))
        end = max(planned.mapped('date_planned_end'))
        span = max((end - start).days, 1)
        pts = []
        for i in range(samples + 1):
            x = i / samples
            t = start + timedelta(days=round(span * x))
            pv = sum(s.estimate_value * planned_fraction(
                t, s.date_planned_start, s.date_planned_end,
                s.planned_curve) for s in planned)
            pts.append((x, pv))
        today_x = (today - start).days / span
        return evm_svg.s_curve(
            pts, p.total_ev, p.total_ac, today_x)

    def action_open_structures(self):
        """Drill-down: mở list hạng mục vượt chi của dự án."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Hạng mục — Kiểm soát chi phí',
            'res_model': 'rp.structure',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.project_id.id)],
            'context': {'search_default_cost_alert': 1},
        }

    # ==================================================================
    # Client-action data provider (OWL + Syncfusion dashboard)
    # ==================================================================
    @staticmethod
    def _ym(d):
        return '%04d-%02d' % (d.year, d.month)

    @staticmethod
    def _add_month(y, m):
        """(y, m) → tháng kế tiếp."""
        return (y + 1, 1) if m == 12 else (y, m + 1)

    @classmethod
    def _spread_over_months(cls, monthly, s, e, val):
        """Rải tuyến tính ``val`` trên khoảng [s, e] theo số ngày mỗi tháng."""
        total = (e - s).days + 1
        if total <= 0 or not val:
            return
        y, m, seg_start = s.year, s.month, s
        while seg_start <= e:
            ny, nm = cls._add_month(y, m)
            next_first = date(ny, nm, 1)
            seg_end = min(e, next_first - timedelta(days=1))
            seg_days = (seg_end - seg_start).days + 1
            monthly['%04d-%02d' % (y, m)] += val * seg_days / total
            seg_start, y, m = next_first, ny, nm

    def _bucket_by_month(self, records, date_field, amount_field,
                         fallback_field=None):
        """Gộp records → {ym: Σ amount} theo tháng của date_field."""
        out = defaultdict(float)
        for r in records:
            d = r[date_field] or (r[fallback_field] if fallback_field else False)
            if not d:
                continue
            out[self._ym(d)] += r[amount_field] or 0.0
        return out

    def _monthly_pv(self, contracts):
        """PV time-phased: mỗi HĐ rải giá trị theo lịch thi công của HĐ đó.

        Giá trị 1 task = value_HĐ × (ngày KH của task / Σ ngày KH các task).
        Task đó lại rải tuyến tính trên khoảng ngày kế hoạch của nó.
        HĐ không có lịch → dồn toàn bộ giá trị vào tháng bắt đầu dự án.
        """
        monthly = defaultdict(float)
        Task = self.env['project.task']
        for c in contracts:
            val = c.contract_value_total or 0.0
            if not val:
                continue
            tasks = Task.search([
                ('rp_contract_id', '=', c.id),
                ('is_milestone', '=', False),
                ('planned_start', '!=', False),
                ('planned_end', '!=', False),
            ])
            total_days = sum(
                max((t.planned_end - t.planned_start).days + 1, 1)
                for t in tasks)
            if not total_days:
                # không có lịch → đặt tại ngày bắt đầu HĐ (hoặc hôm nay)
                d0 = c.date_start or fields.Date.context_today(self)
                monthly[self._ym(d0)] += val
                continue
            for t in tasks:
                tdays = max((t.planned_end - t.planned_start).days + 1, 1)
                self._spread_over_months(
                    monthly, t.planned_start, t.planned_end,
                    val * tdays / total_days)
        return monthly

    @api.model
    def get_evm_dashboard(self, project_id=None):
        """Trả JSON cho client action ``rp_evm.dashboard``.

        Mọi con số tính trực tiếp từ chứng từ nguồn của dự án:
          BAC = Σ HĐ thầu phụ · EV = BBN nghiệm thu đã duyệt ·
          AC  = hóa đơn nhà thầu (posted) qua mốc thanh toán ·
          PV  = giá trị HĐ rải theo lịch thi công.
        """
        Project = self.env['re.project']
        projects = Project.search([], order='id')
        if project_id:
            project = Project.browse(int(project_id)).exists()
        else:
            # Mặc định = dự án có nhiều dữ liệu EVM sống nhất (số BBN nghiệm
            # thu đã duyệt), tie-break theo tổng giá trị HĐ thầu phụ — để mở
            # ra là thấy ngay đường cong S và các chỉ số.
            self.env.cr.execute("""
                SELECT p.id
                  FROM re_project p
             LEFT JOIN (SELECT project_id, COUNT(*) n
                          FROM rp_progress_acceptance
                         WHERE state = 'approved'
                      GROUP BY project_id) a ON a.project_id = p.id
             LEFT JOIN (SELECT project_id, SUM(contract_value_total) v
                          FROM rp_contract
                         WHERE state NOT IN ('draft', 'cancel', 'cancelled',
                                             'rejected')
                      GROUP BY project_id) c ON c.project_id = p.id
              ORDER BY COALESCE(a.n, 0) DESC, COALESCE(c.v, 0) DESC, p.id
                 LIMIT 1
            """)
            row = self.env.cr.fetchone()
            project = Project.browse(row[0]) if row else projects[:1]
        if not project:
            return {'ok': False}
        pid = project.id
        cur = project.currency_id or self.env.company.currency_id
        today = fields.Date.context_today(self)

        # ---- Gói thầu (BAC) ----
        contracts = self.env['rp.contract'].search([
            ('project_id', '=', pid),
            ('state', 'not in', ('draft', 'cancel', 'cancelled', 'rejected')),
        ])
        bac = sum(contracts.mapped('contract_value_total'))

        # ---- EV (nghiệm thu đã duyệt) ----
        accepts = self.env['rp.progress.acceptance'].search([
            ('project_id', '=', pid), ('state', '=', 'approved')])
        ev = sum(accepts.mapped('total_value_period'))

        # ---- AC (hóa đơn nhà thầu qua mốc thanh toán → HĐ → dự án) ----
        bills = self.env['account.move'].search([
            ('move_type', '=', 'in_invoice'), ('state', '=', 'posted'),
            ('payment_milestone_id.contract_id.project_id', '=', pid)])
        ac = sum(bills.mapped('amount_untaxed'))

        # ---- Chuỗi thời gian theo tháng ----
        pv_m = self._monthly_pv(contracts)
        ev_m = self._bucket_by_month(
            accepts, 'date_approved', 'total_value_period',
            fallback_field='date_submitted')
        ac_m = self._bucket_by_month(bills, 'invoice_date', 'amount_untaxed')

        # Dòng tiền THU (hóa đơn phát hành CĐT) — chỉ khi có rp_owner_contract
        inflow_m = defaultdict(float)
        Move = self.env['account.move']
        if 'owner_project_id' in Move._fields:
            owner_inv = Move.search([
                ('move_type', '=', 'out_invoice'), ('state', '=', 'posted'),
                ('owner_project_id', '=', pid)])
            inflow_m = self._bucket_by_month(
                owner_inv, 'invoice_date', 'amount_untaxed')

        # ---- Trục tháng: từ đầu lịch tới cuối lịch (bao trọn PV) ----
        all_ym = set(pv_m) | set(ev_m) | set(ac_m) | set(inflow_m)
        all_ym.add(self._ym(today))
        if not all_ym:
            return {'ok': False}
        y0, m0 = map(int, min(all_ym).split('-'))
        y1, m1 = map(int, max(all_ym).split('-'))
        months = []
        y, m = y0, m0
        while (y, m) <= (y1, m1):
            months.append('%04d-%02d' % (y, m))
            y, m = self._add_month(y, m)

        cur_ym = self._ym(today)
        pv_cum = ev_cum = ac_cum = inflow_cum = 0.0
        scurve, cash = [], []
        pv_today = 0.0
        for ym in months:
            pv_cum += pv_m.get(ym, 0.0)
            ev_cum += ev_m.get(ym, 0.0)
            ac_cum += ac_m.get(ym, 0.0)
            past = ym <= cur_ym
            if past:
                pv_today = pv_cum
            scurve.append({
                'ym': ym,
                'pv': round(pv_cum, 0),
                # EV/AC chỉ vẽ tới tháng hiện tại (dữ liệu thực)
                'ev': round(ev_cum, 0) if past else None,
                'ac': round(ac_cum, 0) if past else None,
            })
            out = ac_m.get(ym, 0.0)
            inn = inflow_m.get(ym, 0.0)
            inflow_cum += inn
            cash.append({
                'ym': ym, 'inflow': round(inn, 0), 'outflow': round(out, 0),
                'net_cum': round(inflow_cum - ac_cum, 0),
            })

        # ---- Chỉ số ----
        cpi = (ev / ac) if ac else 0.0
        spi = (ev / pv_today) if pv_today else 0.0
        cv = ev - ac
        sv = ev - pv_today
        eac = (bac / cpi) if cpi else bac
        vac = bac - eac
        progress_pct = (ev / bac * 100.0) if bac else 0.0
        budget_used_pct = (ac / bac * 100.0) if bac else 0.0

        def _score(x, lo, hi):          # x→[0,1] tuyến tính, clamp
            if hi == lo:
                return 0.0
            return max(0.0, min(1.0, (x - lo) / (hi - lo)))
        health = round(
            35 * _score(cpi, 0.85, 1.15) + 35 * _score(spi, 0.85, 1.15) + 20)

        # ---- Tiến độ theo gói thầu ----
        packages = [{
            'name': c.display_name,
            'value': round(c.contract_value_total or 0.0, 0),
            'percent': round(c.acceptance_progress_percent or 0.0, 1),
            'contractor': c.contractor_id.display_name if c.contractor_id
            else '',
            'state': c.state,
        } for c in contracts.sorted(
            key=lambda x: x.contract_value_total or 0.0, reverse=True)]

        # ---- Cơ cấu giá trị (donut) theo gói thầu ----
        cost_breakdown = [
            {'name': p['name'], 'value': p['value']} for p in packages]

        # ==============================================================
        # BƯỚC 2 — Rủi ro · An toàn · Chất lượng · Nhân lực · Mốc · Insight
        # ==============================================================
        def _fmt(v):
            v = round(v or 0)
            a = abs(v)
            if a >= 1e9:
                return ('%.1f tỷ' % (v / 1e9)).replace('.0 tỷ', ' tỷ')
            if a >= 1e6:
                return '%.0f tr' % (v / 1e6)
            return '{:,.0f}'.format(v).replace(',', '.')

        proj_start = date(y0, m0, 1) if months else today
        first_task = self.env['project.task'].search(
            [('rp_contract_id', 'in', contracts.ids),
             ('planned_start', '!=', False)],
            order='planned_start', limit=1)
        if first_task:
            proj_start = first_task.planned_start

        # ---- Rủi ro (ma trận 5×5) ----
        Risk = self.env['rp.risk']
        cat_labels = dict(Risk._fields['category'].selection)
        risks = Risk.search([
            ('project_id', '=', pid),
            ('state', 'in', ('open', 'mitigating'))])
        heat = defaultdict(int)
        for r in risks:
            heat[(int(r.probability), int(r.impact))] += 1
        risk_matrix = [[
            {'p': p, 'i': i, 'count': heat.get((p, i), 0), 'score': p * i}
            for i in range(1, 6)] for p in range(5, 0, -1)]
        high_risks = risks.filtered(lambda x: x.level in ('high', 'critical'))
        top_risks = [{
            'name': r.name,
            'category': cat_labels.get(r.category, r.category or ''),
            'level': r.level, 'score': r.score,
            'impact_note': r.impact_note or '',
        } for r in risks.sorted(key=lambda x: x.score, reverse=True)[:6]]

        # ---- An toàn ----
        Incident = self.env['rp.site.incident']
        incidents = Incident.search([('project_id', '=', pid)])

        def _as_date(dt):
            return dt.date() if hasattr(dt, 'date') else dt
        lti = incidents.filtered(
            lambda x: x.incident_type in ('lost_time', 'serious'))
        if lti:
            last_lti = max(_as_date(x.date) for x in lti)
            days_without_lti = max((today - last_lti).days, 0)
        else:
            days_without_lti = max((today - proj_start).days, 0)
        toolbox_count = self.env['rp.site.toolbox'].search_count(
            [('project_id', '=', pid)])
        insp = self.env['rp.site.safety.inspection'].search(
            [('project_id', '=', pid), ('state', '=', 'done')])
        insp_pass = len(insp.filtered(
            lambda x: x.result in ('pass', 'pass_note')))
        safety = {
            'days_without_lti': days_without_lti,
            'incident_count': len(incidents),
            'near_miss': len(incidents.filtered(
                lambda x: x.incident_type == 'near_miss')),
            'lti_count': len(lti),
            'toolbox_count': toolbox_count,
            'safety_pass_pct': round(insp_pass / len(insp) * 100) if insp else 100,
        }

        # ---- Chất lượng (QA/QC) ----
        Punch = self.env['rp.site.punch']
        punches = Punch.search([('project_id', '=', pid)])
        open_punch = punches.filtered(
            lambda x: x.state in ('open', 'in_progress'))
        sev = {s: len(open_punch.filtered(lambda x: x.severity == s))
               for s in ('critical', 'major', 'minor')}
        punch_closed = len(punches.filtered(
            lambda x: x.state in ('fixed', 'closed')))
        qaqc = {
            'open': len(open_punch),
            'critical_open': sev['critical'],
            'overdue': len(open_punch.filtered('is_overdue')),
            'total': len(punches),
            'quality_pct': round(punch_closed / len(punches) * 100) if punches else 100,
            'breakdown': [
                {'name': 'Nghiêm trọng', 'value': sev['critical']},
                {'name': 'Nặng', 'value': sev['major']},
                {'name': 'Nhẹ', 'value': sev['minor']},
            ],
        }

        # ---- Nhân lực (từ nhật ký thi công) ----
        diaries = self.env['rp.site.diary'].search(
            [('project_id', '=', pid), ('total_manpower', '>', 0)], order='date')
        mp = defaultdict(int)
        for d in diaries:
            mp[d.date] += d.total_manpower
        manpower = [{'date': dt.strftime('%Y-%m-%d'), 'count': int(v)}
                    for dt, v in sorted(mp.items())]
        avg_mp = round(sum(mp.values()) / len(mp)) if mp else 0
        peak_mp = max(mp.values()) if mp else 0

        # ---- Mốc tiến độ ----
        ms = self.env['project.task'].search(
            [('rp_contract_id', 'in', contracts.ids),
             ('is_milestone', '=', True)], order='planned_end')
        milestones = []
        for m in ms[:8]:
            md = m.planned_end or m.planned_start
            pctm = m.progress_percent or 0.0
            status = ('done' if pctm >= 100 else
                      'overdue' if (m.planned_end and m.planned_end < today
                                    and pctm < 100) else 'ontrack')
            milestones.append({
                'name': m.name,
                'date': md.strftime('%d/%m/%Y') if md else '',
                'percent': round(pctm), 'status': status,
            })

        # ---- Cảnh báo & khuyến nghị (tự động) ----
        insights = []
        if cpi and cpi < 0.95:
            insights.append({'type': 'danger', 'icon': '⚠',
                'title': 'Chi phí vượt kế hoạch',
                'text': 'CPI %.2f (<1) — chi phí thực cao hơn giá trị làm '
                        'ra. Rà soát gói vượt chi, siết dự toán còn lại.' % cpi})
        elif cpi >= 1.0:
            insights.append({'type': 'good', 'icon': '✓',
                'title': 'Chi phí trong tầm kiểm soát',
                'text': 'CPI %.2f — hiệu quả chi phí tốt; dự báo tiết kiệm '
                        '%s so với ngân sách.' % (cpi, _fmt(vac))})
        if spi and spi < 0.95:
            insights.append({'type': 'warn', 'icon': '◷',
                'title': 'Tiến độ chậm kế hoạch',
                'text': 'SPI %.2f — giá trị làm ra thấp hơn kế hoạch %s. '
                        'Cân nhắc tăng ca/bổ sung mũi thi công.'
                        % (spi, _fmt(abs(sv)))})
        elif spi >= 1.05:
            insights.append({'type': 'good', 'icon': '✓',
                'title': 'Tiến độ vượt kế hoạch',
                'text': 'SPI %.2f — đang nhanh hơn kế hoạch.' % spi})
        if high_risks:
            nm = ', '.join(high_risks.sorted(
                key=lambda x: x.score, reverse=True)[:3].mapped('name'))
            insights.append({'type': 'danger', 'icon': '⚠',
                'title': '%d rủi ro cao/nghiêm trọng' % len(high_risks),
                'text': '%s — cần kế hoạch giảm thiểu và người phụ trách.' % nm})
        if qaqc['critical_open']:
            insights.append({'type': 'warn', 'icon': '▦',
                'title': '%d lỗi chất lượng nghiêm trọng đang mở'
                         % qaqc['critical_open'],
                'text': 'Phải khắc phục trước khi nghiệm thu giai đoạn.'})
        if qaqc['overdue']:
            insights.append({'type': 'warn', 'icon': '▦',
                'title': '%d lỗi QA/QC quá hạn khắc phục' % qaqc['overdue'],
                'text': 'Đôn đốc nhà thầu đóng lỗi đúng hạn cam kết.'})
        if safety['days_without_lti'] >= 90:
            insights.append({'type': 'good', 'icon': '✓',
                'title': '%d ngày không tai nạn mất ngày công'
                         % safety['days_without_lti'],
                'text': 'Duy trì tốt kỷ luật an toàn hiện trường.'})
        elif safety['lti_count']:
            insights.append({'type': 'warn', 'icon': '⛑',
                'title': 'Có %d sự cố mất ngày công' % safety['lti_count'],
                'text': 'Rà soát biện pháp an toàn, tăng tần suất toolbox '
                        'meeting.'})

        return {
            'ok': True,
            'currency': {'symbol': cur.symbol or '₫',
                         'position': cur.position or 'after'},
            'projects': [{'id': p.id, 'name': p.display_name}
                         for p in projects],
            'project': {
                'id': pid, 'name': project.display_name,
                'today': today.strftime('%d/%m/%Y'),
                'today_ym': cur_ym,
            },
            'kpi': {
                'bac': round(bac, 0), 'ev': round(ev, 0), 'ac': round(ac, 0),
                'cv': round(cv, 0), 'sv': round(sv, 0),
                'cpi': round(cpi, 3), 'spi': round(spi, 3),
                'eac': round(eac, 0), 'vac': round(vac, 0),
                'pv_today': round(pv_today, 0),
                'progress_pct': round(progress_pct, 1),
                'budget_used_pct': round(budget_used_pct, 1),
                'health': health,
                'contract_count': len(contracts),
                'accept_count': len(accepts),
                'bill_count': len(bills),
            },
            'scurve': scurve,
            'cashflow': cash,
            'packages': packages,
            'cost_breakdown': cost_breakdown,
            # ---- Bước 2 ----
            'risk': {
                'open_count': len(risks),
                'high_count': len(high_risks),
                'matrix': risk_matrix,
                'top': top_risks,
            },
            'safety': safety,
            'qaqc': qaqc,
            'manpower': {
                'series': manpower, 'avg': avg_mp, 'peak': peak_mp,
            },
            'milestones': milestones,
            'insights': insights,
        }
