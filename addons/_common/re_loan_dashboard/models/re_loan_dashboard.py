# -*- coding: utf-8 -*-
"""Realty Loan Dashboard — KPI tổng hợp toàn bộ nghiệp vụ Quản lý Vay.

Pattern: TransientModel singleton-ish. User click menu "Quản lý Vay" →
override action mở dashboard → default_get() compute realtime KPIs.
"""
from datetime import timedelta

from odoo import _, api, fields, models


class ReLoanDashboard(models.TransientModel):
    _name = 're.loan.dashboard'
    _description = 'Realty Loan — Dashboard KPI'

    @api.depends_context('lang')
    def _compute_display_name(self):
        # Override default Odoo display_name (auto = "re.loan.dashboard,
        # NewId_0x...") cho breadcrumb. TransientModel singleton-ish
        # KHÔNG persist → không có name field, fallback xấu.
        for rec in self:
            rec.display_name = 'Quản lý Vay — Dashboard'

    # ─── 1. HĐTD ───────────────────────────────────────────────────
    kpi_hdtd_active = fields.Integer(string='HĐTD đang hiệu lực')
    kpi_hdtd_total_limit = fields.Monetary(string='Tổng hạn mức HĐTD')
    kpi_hdtd_facility_granted = fields.Monetary(
        string='Đã cấp cho facility')
    kpi_hdtd_remaining = fields.Monetary(string='HĐTD còn chưa cấp')
    kpi_hdtd_expiring_90d = fields.Integer(
        string='HĐTD sắp hết hạn ≤90 ngày')

    # ─── 2. Facility split cho vay vs bảo lãnh ────────────────────
    kpi_facility_loan_limit = fields.Monetary(string='Σ HM cho vay')
    kpi_facility_loan_used = fields.Monetary(string='Đã cho vay')
    kpi_facility_loan_avail = fields.Monetary(string='Cho vay còn lại')
    kpi_facility_loan_used_pct = fields.Float(
        string='% HM cho vay đã dùng')
    kpi_facility_bg_limit = fields.Monetary(string='Σ HM bảo lãnh')
    kpi_facility_bg_used = fields.Monetary(string='Đã bảo lãnh')
    kpi_facility_bg_avail = fields.Monetary(string='Bảo lãnh còn lại')
    kpi_facility_bg_used_pct = fields.Float(
        string='% HM bảo lãnh đã dùng')

    # ─── 3. KW (Khế ước) ──────────────────────────────────────────
    kpi_kw_active = fields.Integer(string='KW còn dư nợ')
    kpi_kw_principal_outstanding = fields.Monetary(string='Σ dư nợ gốc')
    kpi_kw_interest_paid_ytd = fields.Monetary(
        string='Lãi đã trả YTD',
        help='Σ amount_paid của interest_line trong năm hiện tại.')
    kpi_kw_maturing_30d = fields.Integer(
        string='KW sắp đáo hạn ≤30 ngày')
    kpi_kw_maturing_90d = fields.Integer(
        string='KW sắp đáo hạn ≤90 ngày')

    # ─── 4. Bảo lãnh ──────────────────────────────────────────────
    kpi_bg_outstanding = fields.Monetary(string='Σ BL outstanding')
    kpi_bg_count_active = fields.Integer(string='Số BL active')
    kpi_bg_expiring_30d = fields.Integer(string='BL sắp hết hạn ≤30 ngày')

    # ─── 5. Pending workflow ──────────────────────────────────────
    kpi_pending_disbursement = fields.Integer(
        string='Hồ sơ giải ngân chờ duyệt',
        help='Hồ sơ giải ngân state ∈ {draft, submitted}.')
    kpi_pending_bank_advice = fields.Integer(
        string='Giấy báo nợ chờ áp dụng',
        help='Bank advice state = draft (chưa post → chưa tạo repayment).')
    kpi_pending_bg_request = fields.Integer(
        string='Đề nghị BL chờ phát hành',
        help='re.guarantee.request state đang chờ.')

    # ─── 6. Cảnh báo ──────────────────────────────────────────────
    kpi_alert_kw_overdue = fields.Integer(string='⚠ KW quá hạn')
    kpi_alert_kw_overdue_amount = fields.Monetary(
        string='⚠ Dư nợ KW quá hạn')
    kpi_alert_bg_expired = fields.Integer(string='⚠ BL hết hạn chưa gia hạn')
    kpi_alert_interest_overdue = fields.Integer(
        string='⚠ Kỳ lãi quá hạn chưa trả',
        help='Interest line state ∈ {accrued, partial_paid}, date_due < today.')

    currency_id = fields.Many2one(
        'res.currency', default=lambda s: s.env.company.currency_id)

    # ─── Charts (SVG render server-side) ──────────────────────────
    chart_facility_svg = fields.Html(
        string='Cơ cấu hạn mức', sanitize=False, readonly=True)
    chart_debt_by_bank_svg = fields.Html(
        string='Dư nợ theo ngân hàng', sanitize=False, readonly=True)
    chart_maturity_svg = fields.Html(
        string='KW đáo hạn theo mốc', sanitize=False, readonly=True)
    chart_gauges_svg = fields.Html(
        string='Tỷ lệ sử dụng hạn mức', sanitize=False, readonly=True)
    chart_bg_by_type_svg = fields.Html(
        string='Bảo lãnh theo loại', sanitize=False, readonly=True)

    # ─── Default get — compute KPIs ───────────────────────────────
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        today = fields.Date.context_today(self)
        in_30d = today + timedelta(days=30)
        in_90d = today + timedelta(days=90)
        year_start = today.replace(month=1, day=1)

        # 1. HĐTD
        HDTD = self.env['re.loan.credit.contract']
        active_hdtd = HDTD.search([('state', '=', 'active')])
        res['kpi_hdtd_active'] = len(active_hdtd)
        res['kpi_hdtd_total_limit'] = sum(
            active_hdtd.mapped('amount_total') or [0])
        res['kpi_hdtd_facility_granted'] = sum(
            active_hdtd.mapped('amount_facility_total') or [0])
        res['kpi_hdtd_remaining'] = sum(
            active_hdtd.mapped('amount_facility_available') or [0])
        res['kpi_hdtd_expiring_90d'] = len(active_hdtd.filtered(
            lambda h: h.date_end and today <= h.date_end <= in_90d))

        # 2. Facility split — gộp từ active HĐTD
        loan_lim = sum(active_hdtd.mapped('amount_loan_limit') or [0])
        loan_used = sum(active_hdtd.mapped('amount_loan_used') or [0])
        bg_lim = sum(active_hdtd.mapped('amount_bg_limit') or [0])
        bg_used = sum(active_hdtd.mapped('amount_bg_used') or [0])
        res['kpi_facility_loan_limit'] = loan_lim
        res['kpi_facility_loan_used'] = loan_used
        res['kpi_facility_loan_avail'] = loan_lim - loan_used
        # widget="percentage" trên view tự x100, KHÔNG x trong compute
        # (Odoo convention: percentage field 0-1 range, 0.5 = hiển thị 50%)
        res['kpi_facility_loan_used_pct'] = (
            (loan_used / loan_lim) if loan_lim else 0.0)
        res['kpi_facility_bg_limit'] = bg_lim
        res['kpi_facility_bg_used'] = bg_used
        res['kpi_facility_bg_avail'] = bg_lim - bg_used
        res['kpi_facility_bg_used_pct'] = (
            (bg_used / bg_lim) if bg_lim else 0.0)

        # 3. KW
        Note = self.env['re.loan.note']
        active_notes = Note.search([
            ('state', 'in', ('active', 'partial_paid'))])
        res['kpi_kw_active'] = len(active_notes)
        res['kpi_kw_principal_outstanding'] = sum(
            active_notes.mapped('principal_outstanding') or [0])
        res['kpi_kw_maturing_30d'] = len(active_notes.filtered(
            lambda n: n.date_maturity
            and today <= n.date_maturity <= in_30d
            and (n.principal_outstanding or 0) > 0))
        res['kpi_kw_maturing_90d'] = len(active_notes.filtered(
            lambda n: n.date_maturity
            and today <= n.date_maturity <= in_90d
            and (n.principal_outstanding or 0) > 0))

        # Lãi đã trả YTD — lọc theo date_to (ngày kết thúc kỳ tính lãi)
        # re.loan.note.interest.line schema: date_from / date_to, KHÔNG
        # có date_due. State paid/partial_paid → amount_interest_paid
        # là số lãi customer đã trả thực sự.
        InterestLine = self.env['re.loan.note.interest.line']
        paid_lines_ytd = InterestLine.search([
            ('date_to', '>=', year_start),
            ('date_to', '<=', today),
            ('state', 'in', ('paid', 'partial_paid')),
        ])
        res['kpi_kw_interest_paid_ytd'] = sum(
            paid_lines_ytd.mapped('amount_interest_paid') or [0])

        # 4. Bảo lãnh
        BG = self.env['re.bank.guarantee']
        active_bg = BG.search([('state', 'in', ('issued', 'extended'))])
        res['kpi_bg_count_active'] = len(active_bg)
        res['kpi_bg_outstanding'] = sum(active_bg.mapped('amount') or [0])
        res['kpi_bg_expiring_30d'] = len(active_bg.filtered(
            lambda g: g.date_expiry and today <= g.date_expiry <= in_30d))

        # 5. Pending workflow
        Dossier = self.env['rp.loan.disbursement.dossier'] \
            if 'rp.loan.disbursement.dossier' in self.env else None
        if Dossier:
            res['kpi_pending_disbursement'] = Dossier.search_count([
                ('state', 'in', ('draft', 'submitted'))])
        else:
            res['kpi_pending_disbursement'] = 0

        BankAdvice = self.env['re.loan.bank.advice']
        res['kpi_pending_bank_advice'] = BankAdvice.search_count([
            ('state', '=', 'draft')])

        if 're.guarantee.request' in self.env:
            BGRequest = self.env['re.guarantee.request']
            res['kpi_pending_bg_request'] = BGRequest.search_count([
                ('state', 'not in', ('issued', 'cancelled', 'rejected'))])
        else:
            res['kpi_pending_bg_request'] = 0

        # 6. Cảnh báo
        overdue_kws = active_notes.filtered(
            lambda n: n.date_maturity and n.date_maturity < today
            and (n.principal_outstanding or 0) > 0)
        res['kpi_alert_kw_overdue'] = len(overdue_kws)
        res['kpi_alert_kw_overdue_amount'] = sum(
            overdue_kws.mapped('principal_outstanding') or [0])
        res['kpi_alert_bg_expired'] = len(active_bg.filtered(
            lambda g: g.date_expiry and g.date_expiry < today))
        # Lãi quá hạn chưa trả
        overdue_lines = InterestLine.search([
            ('state', 'in', ('accrued', 'partial_paid')),
            ('date_to', '<', today),
        ])
        res['kpi_alert_interest_overdue'] = len(overdue_lines)

        # ─── Charts ───────────────────────────────────────────────
        res.update(self._build_charts(
            active_hdtd, active_notes, active_bg, today))
        return res

    def _build_charts(self, active_hdtd, active_notes, active_bg, today):
        """Sinh SVG cho các chart dashboard (CC1 — dashboard hoành tráng)."""
        from . import svg_charts as C
        out = {}

        # 1. Gauge đôi — % HM cho vay + % HM bảo lãnh đã dùng
        loan_lim = sum(active_hdtd.mapped('amount_loan_limit') or [0])
        loan_used = sum(active_hdtd.mapped('amount_loan_used') or [0])
        bg_lim = sum(active_hdtd.mapped('amount_bg_limit') or [0])
        bg_used = sum(active_hdtd.mapped('amount_bg_used') or [0])
        out['chart_gauges_svg'] = (
            '<div style="display:flex;gap:24px;flex-wrap:wrap;'
            'align-items:center">%s%s</div>' % (
                C.donut(loan_used, loan_lim, 'Cho vay', '#1B6CA8', 160),
                C.donut(bg_used, bg_lim, 'Bảo lãnh', '#F2A93B', 160)))

        # 2. Stacked — cơ cấu HĐTD: đã cho vay / đã bảo lãnh / còn trống
        total_hdtd = sum(active_hdtd.mapped('amount_total') or [0])
        free = max(0, total_hdtd - loan_used - bg_used)
        out['chart_facility_svg'] = C.stacked_bar([
            ('Đã cho vay', loan_used, '#1B6CA8'),
            ('Đã bảo lãnh', bg_used, '#F2A93B'),
            ('Còn trống', free, '#CBD6DE'),
        ], width=460, height=58)

        # 3. Hbar — dư nợ gốc theo ngân hàng (top 6)
        by_bank = {}
        for n in active_notes:
            bank = n.partner_id.name or '(không rõ)'
            by_bank[bank] = by_bank.get(bank, 0) + (
                n.principal_outstanding or 0)
        top = sorted(by_bank.items(), key=lambda x: -x[1])[:6]
        out['chart_debt_by_bank_svg'] = C.hbar(top, width=460, unit='money')

        # 4. Vbar — KW đáo hạn theo mốc thời gian
        buckets = {'Quá hạn': 0, '≤30 ngày': 0, '31-90 ngày': 0,
                   '91-180 ngày': 0, '>180 ngày': 0}
        for n in active_notes:
            if not (n.date_maturity and (n.principal_outstanding or 0) > 0):
                continue
            d = (n.date_maturity - today).days
            if d < 0:
                buckets['Quá hạn'] += 1
            elif d <= 30:
                buckets['≤30 ngày'] += 1
            elif d <= 90:
                buckets['31-90 ngày'] += 1
            elif d <= 180:
                buckets['91-180 ngày'] += 1
            else:
                buckets['>180 ngày'] += 1
        out['chart_maturity_svg'] = C.vbar(
            list(buckets.items()), width=460, height=210, unit='count')

        # 5. Hbar — BL outstanding theo loại (guarantee_type nếu có)
        by_type = {}
        for g in active_bg:
            t = (dict(g._fields['guarantee_type'].selection).get(
                g.guarantee_type, g.guarantee_type)
                if 'guarantee_type' in g._fields and g.guarantee_type
                else 'Khác')
            by_type[t] = by_type.get(t, 0) + (g.amount or 0)
        out['chart_bg_by_type_svg'] = C.hbar(
            sorted(by_type.items(), key=lambda x: -x[1])[:6],
            width=460, unit='money')
        return out

    # ─── Drill-down actions ───────────────────────────────────────
    def _act(self, name, model, domain=None):
        return {
            'type': 'ir.actions.act_window',
            'name': _(name),
            'res_model': model,
            'view_mode': 'list,form',
            'domain': domain or [],
        }

    def action_open_hdtd_active(self):
        return self._act('HĐTD hiệu lực', 're.loan.credit.contract',
                         [('state', '=', 'active')])

    def action_open_hdtd_expiring(self):
        today = fields.Date.context_today(self)
        in_90d = today + timedelta(days=90)
        return self._act('HĐTD sắp hết hạn ≤90d', 're.loan.credit.contract', [
            ('state', '=', 'active'),
            ('date_end', '>=', today),
            ('date_end', '<=', in_90d),
        ])

    def action_open_facilities_loan(self):
        return self._act('Hạn mức cho vay', 're.loan.facility',
                         [('purpose', '!=', 'bank_guarantee')])

    def action_open_facilities_bg(self):
        return self._act('Hạn mức bảo lãnh', 're.loan.facility',
                         [('purpose', '=', 'bank_guarantee')])

    def action_open_kw_active(self):
        return self._act('KW còn dư nợ', 're.loan.note',
                         [('state', 'in', ('active', 'partial_paid'))])

    def action_open_kw_maturing_30d(self):
        today = fields.Date.context_today(self)
        in_30d = today + timedelta(days=30)
        return self._act('KW sắp đáo hạn ≤30d', 're.loan.note', [
            ('state', 'in', ('active', 'partial_paid')),
            ('date_maturity', '>=', today),
            ('date_maturity', '<=', in_30d),
            ('principal_outstanding', '>', 0),
        ])

    def action_open_kw_maturing_90d(self):
        today = fields.Date.context_today(self)
        in_90d = today + timedelta(days=90)
        return self._act('KW sắp đáo hạn ≤90d', 're.loan.note', [
            ('state', 'in', ('active', 'partial_paid')),
            ('date_maturity', '>=', today),
            ('date_maturity', '<=', in_90d),
            ('principal_outstanding', '>', 0),
        ])

    def action_open_kw_overdue(self):
        today = fields.Date.context_today(self)
        return self._act('⚠ KW quá hạn', 're.loan.note', [
            ('state', 'in', ('active', 'partial_paid')),
            ('date_maturity', '<', today),
            ('principal_outstanding', '>', 0),
        ])

    def action_open_bg_active(self):
        return self._act('BL outstanding', 're.bank.guarantee',
                         [('state', 'in', ('issued', 'extended'))])

    def action_open_bg_expiring(self):
        today = fields.Date.context_today(self)
        in_30d = today + timedelta(days=30)
        return self._act('BL sắp hết hạn ≤30d', 're.bank.guarantee', [
            ('state', 'in', ('issued', 'extended')),
            ('date_expiry', '>=', today),
            ('date_expiry', '<=', in_30d),
        ])

    def action_open_bg_expired(self):
        today = fields.Date.context_today(self)
        return self._act('⚠ BL hết hạn chưa gia hạn', 're.bank.guarantee', [
            ('state', 'in', ('issued', 'extended')),
            ('date_expiry', '<', today),
        ])

    def action_open_pending_disbursement(self):
        if 'rp.loan.disbursement.dossier' not in self.env:
            return False
        return self._act('Giải ngân chờ duyệt',
                         'rp.loan.disbursement.dossier',
                         [('state', 'in', ('draft', 'submitted'))])

    def action_open_pending_bank_advice(self):
        return self._act('Giấy báo nợ chờ áp dụng', 're.loan.bank.advice',
                         [('state', '=', 'draft')])

    def action_open_pending_bg_request(self):
        if 're.guarantee.request' not in self.env:
            return False
        return self._act('Đề nghị BL chờ phát hành', 're.guarantee.request',
                         [('state', 'not in', ('issued', 'cancelled', 'rejected'))])

    def action_open_interest_overdue(self):
        today = fields.Date.context_today(self)
        return self._act('⚠ Kỳ lãi quá hạn chưa trả',
                         're.loan.note.interest.line', [
                             ('state', 'in', ('accrued', 'partial_paid')),
                             ('date_to', '<', today),
                         ])

    def action_refresh(self):
        new_record = self.create({})
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': new_record.id,
            'view_mode': 'form',
            'view_id': self.env.ref(
                're_loan_dashboard.view_re_loan_dashboard_form').id,
            'target': 'main',
        }
