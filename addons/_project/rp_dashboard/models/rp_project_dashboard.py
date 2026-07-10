# -*- coding: utf-8 -*-
"""Realty Project Dashboard — KPI tổng hợp + drill-down.

Pattern: TransientModel singleton-ish. Mỗi lần user mở menu Dashboard,
hệ thống tạo 1 record mới với default_get() compute KPIs từ
realtime DB query. KHÔNG persist — bảng transient garbage collect 30
phút sau.

Tại sao không dùng SearchPanel/Pivot có sẵn của Odoo? Vì KPI cross
nhiều model (re.project + rp.contract + re.loan.note + re.bank.guarantee)
— UI built-in chỉ work 1 model/lúc.
"""
from datetime import date, timedelta

from odoo import _, api, fields, models


class RpProjectDashboard(models.TransientModel):
    _name = 'rp.project.dashboard'
    _description = 'Realty Project — Dashboard KPI'

    @api.depends_context('lang')
    def _compute_display_name(self):
        # Override default Odoo "rp.project.dashboard,NewId_0x..."
        # cho breadcrumb. TransientModel singleton-ish KHÔNG persist
        # → không có name field, fallback xấu.
        for rec in self:
            rec.display_name = 'Realty Project — Dashboard'

    # ─── 1. Dự án ──────────────────────────────────────────────────
    kpi_project_active = fields.Integer(
        string='Dự án đang triển khai',
        help='Số dự án active (không archived).')
    kpi_project_selling = fields.Integer(
        string='Dự án đang mở bán',
        help='Số dự án có `is_open_for_sale = True`.')

    # ─── 2. HĐ thầu ────────────────────────────────────────────────
    kpi_contract_executing = fields.Integer(
        string='HĐ thầu đang thi công',
        help='rp.contract state ∈ {signed, executing}.')
    kpi_contract_total_value = fields.Monetary(
        string='Tổng giá trị HĐ thầu',
        help='Σ contract_value_total của HĐ ∈ {signed, executing, completed}.')
    kpi_contract_paid_pct = fields.Float(
        string='% đã thanh toán HĐ',
        help='Tổng tiền đã thanh toán / Tổng giá trị HĐ × 100.')

    # ─── 3. Tạm ứng ────────────────────────────────────────────────
    kpi_advance_to_approve = fields.Integer(
        string='Tạm ứng chờ duyệt',
        help='rp.advance.payment state = to_approve. Highlight ĐỎ.')
    kpi_advance_paid_total = fields.Monetary(
        string='Tổng Tạm ứng đã giải ngân',
        help='Σ amount của TƯ state = paid (chưa cấn trừ đủ).')
    kpi_advance_pending_settle = fields.Integer(
        string='TƯ chưa cấn trừ đủ',
        help='Số TƯ state = paid, amount_settled < amount.')

    # ─── 4. Vay HĐTD ───────────────────────────────────────────────
    kpi_loan_outstanding = fields.Monetary(
        string='Tổng dư nợ gốc (KW)',
        help='Σ principal_outstanding của các KW state ∈ {active, partial_paid}.')
    kpi_loan_maturing_30d = fields.Integer(
        string='KW sắp đáo hạn ≤30 ngày',
        help='KW có date_maturity trong 30 ngày tới + còn dư nợ.')
    kpi_loan_facility_used_pct = fields.Float(
        string='% hạn mức HĐTD đã dùng',
        help='Σ amount_used / Σ contract_value_total HĐTD active × 100.')

    # ─── 5. Bảo lãnh ───────────────────────────────────────────────
    kpi_bg_outstanding = fields.Monetary(
        string='Σ BL outstanding',
        help='Σ amount BL state ∈ {issued, extended}.')
    kpi_bg_expiring_30d = fields.Integer(
        string='BL sắp hết hạn ≤30 ngày',
        help='BL còn issued/extended, date_expiry trong 30 ngày tới.')

    # ─── 6. Cảnh báo ───────────────────────────────────────────────
    kpi_alert_loan_overdue = fields.Integer(
        string='⚠ KW quá hạn',
        help='KW có date_maturity < today + còn dư nợ.')
    kpi_alert_bg_expired = fields.Integer(
        string='⚠ BL hết hạn chưa gia hạn',
        help='BL state ∈ {issued, extended}, date_expiry < today.')
    kpi_alert_contract_no_progress = fields.Integer(
        string='⚠ HĐ chậm tiến độ',
        help='HĐ state = executing nhưng không có cập nhật tiến độ '
             '30 ngày gần nhất. (TODO: cần rp_progress hook)')

    currency_id = fields.Many2one(
        'res.currency', default=lambda s: s.env.company.currency_id)

    show_advance = fields.Boolean(
        string='Hiện khối Tạm ứng',
        help='False khi module Tạm ứng chưa cài hoặc user không thuộc '
             'nhóm Tạm ứng — ẩn khối thay vì hiện 0 gây hiểu nhầm.')

    # ─── Helper quyền ─────────────────────────────────────────────
    def _kpi_model(self, model_name):
        """Model để tính KPI, hoặc None nếu không dùng được.

        None khi (a) module chưa cài, hoặc (b) user không có quyền đọc
        model đó. Dashboard gom nhiều phân hệ nên phải xuống cấp mềm:
        một chủ đầu tư chỉ có quyền Dự án/HĐ thầu/Tạm ứng vẫn mở được
        dashboard — KPI ngoài quyền trả 0 và bị ẩn ở view, thay vì ném
        AccessError làm vỡ cả trang.

        CHÚ Ý: giá trị trả về là recordset RỖNG (falsy) — nơi gọi phải
        so ``is not None``, tuyệt đối không dùng ``if Model:``.
        """
        if model_name not in self.env:
            return None
        Model = self.env[model_name]
        return Model if Model.has_access('read') else None

    # ─── Default get — compute KPIs khi mở dashboard ──────────────
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        today = fields.Date.context_today(self)
        in_30d = today + timedelta(days=30)

        # 1. Dự án
        Project = self._kpi_model('re.project')
        res['kpi_project_active'] = (
            Project.search_count([]) if Project is not None else 0)
        res['kpi_project_selling'] = (
            Project.search_count([('is_open_for_sale', '=', True)])
            if Project is not None else 0)

        # 2. HĐ thầu
        Contract = self._kpi_model('rp.contract')
        if Contract is not None:
            contracts_running = Contract.search([
                ('state', 'in', ('signed', 'executing'))])
            contracts_with_value = Contract.search([
                ('state', 'in', ('signed', 'executing', 'completed'))])
            res['kpi_contract_executing'] = len(contracts_running)
            contract_value_total = sum(contracts_with_value.mapped('contract_value_total') or [0])
            amount_paid = sum(contracts_with_value.mapped('amount_paid') or [0])
            res['kpi_contract_total_value'] = contract_value_total
            # widget="percentage" tự x100 — KHÔNG x trong compute
            res['kpi_contract_paid_pct'] = (
                (amount_paid / contract_value_total) if contract_value_total else 0.0)
        else:
            res['kpi_contract_executing'] = 0
            res['kpi_contract_total_value'] = 0
            res['kpi_contract_paid_pct'] = 0.0

        # 3. Tạm ứng — module soft-depend + quyền riêng (nhóm Tạm ứng)
        Advance = self._kpi_model('rp.advance.payment')
        res['show_advance'] = Advance is not None
        if Advance is not None:
            res['kpi_advance_to_approve'] = Advance.search_count([
                ('state', '=', 'to_approve')])
            paid_advances = Advance.search([('state', '=', 'paid')])
            res['kpi_advance_paid_total'] = sum(
                paid_advances.mapped('amount') or [0])
            res['kpi_advance_pending_settle'] = len(paid_advances.filtered(
                lambda a: (a.amount_settled or 0) < (a.amount or 0)))
        else:
            res['kpi_advance_to_approve'] = 0
            res['kpi_advance_paid_total'] = 0
            res['kpi_advance_pending_settle'] = 0

        # 4. Vay HĐTD — cảnh báo quá hạn tính luôn trong block này
        Note = self._kpi_model('re.loan.note')
        if Note is not None:
            active_notes = Note.search([
                ('state', 'in', ('active', 'partial_paid'))])
            res['kpi_loan_outstanding'] = sum(
                active_notes.mapped('principal_outstanding') or [0])
            res['kpi_loan_maturing_30d'] = len(active_notes.filtered(
                lambda n: n.date_maturity
                and today <= n.date_maturity <= in_30d
                and (n.principal_outstanding or 0) > 0))
            res['kpi_alert_loan_overdue'] = len(active_notes.filtered(
                lambda n: n.date_maturity and n.date_maturity < today
                and (n.principal_outstanding or 0) > 0))
        else:
            res['kpi_loan_outstanding'] = 0
            res['kpi_loan_maturing_30d'] = 0
            res['kpi_alert_loan_overdue'] = 0

        Contract_HD = self._kpi_model('re.loan.credit.contract')
        if Contract_HD is not None:
            active_hdtd = Contract_HD.search([('state', '=', 'active')])
            # HĐTD field tên `amount_total`, KHÁC rp.contract dùng
            # `contract_value_total`.
            total_facility = sum(active_hdtd.mapped('amount_total') or [0])
            used_facility = sum(active_hdtd.mapped('amount_pool_used') or [0])
            res['kpi_loan_facility_used_pct'] = (
                (used_facility / total_facility) if total_facility else 0.0)
        else:
            res['kpi_loan_facility_used_pct'] = 0.0

        # 5. Bảo lãnh — cảnh báo hết hạn tính luôn trong block này
        BG = self._kpi_model('re.bank.guarantee')
        if BG is not None:
            active_bg = BG.search([('state', 'in', ('issued', 'extended'))])
            res['kpi_bg_outstanding'] = sum(active_bg.mapped('amount') or [0])
            res['kpi_bg_expiring_30d'] = len(active_bg.filtered(
                lambda g: g.date_expiry and today <= g.date_expiry <= in_30d))
            res['kpi_alert_bg_expired'] = len(active_bg.filtered(
                lambda g: g.date_expiry and g.date_expiry < today))
        else:
            res['kpi_bg_outstanding'] = 0
            res['kpi_bg_expiring_30d'] = 0
            res['kpi_alert_bg_expired'] = 0

        # 6. Cảnh báo còn lại
        # TODO khi rp_progress xong: track lần update progress gần nhất
        res['kpi_alert_contract_no_progress'] = 0

        return res

    # ─── Drill-down actions ────────────────────────────────────────
    def action_open_projects(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Dự án'),
            'res_model': 're.project',
            'view_mode': 'list,form',
        }

    def action_open_contracts_executing(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('HĐ thầu đang thi công'),
            'res_model': 'rp.contract',
            'view_mode': 'list,form',
            'domain': [('state', 'in', ('signed', 'executing'))],
        }

    def action_open_advances_to_approve(self):
        if self._kpi_model('rp.advance.payment') is None:
            return False
        return {
            'type': 'ir.actions.act_window',
            'name': _('Tạm ứng chờ duyệt'),
            'res_model': 'rp.advance.payment',
            'view_mode': 'list,form',
            'domain': [('state', '=', 'to_approve')],
        }

    def action_open_loans_outstanding(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('KW còn dư nợ'),
            'res_model': 're.loan.note',
            'view_mode': 'list,form',
            'domain': [('state', 'in', ('active', 'partial_paid'))],
        }

    def action_open_loans_maturing(self):
        today = fields.Date.context_today(self)
        in_30d = today + timedelta(days=30)
        return {
            'type': 'ir.actions.act_window',
            'name': _('KW sắp đáo hạn ≤30 ngày'),
            'res_model': 're.loan.note',
            'view_mode': 'list,form',
            'domain': [
                ('state', 'in', ('active', 'partial_paid')),
                ('date_maturity', '>=', today),
                ('date_maturity', '<=', in_30d),
                ('principal_outstanding', '>', 0),
            ],
        }

    def action_open_loans_overdue(self):
        today = fields.Date.context_today(self)
        return {
            'type': 'ir.actions.act_window',
            'name': _('⚠ KW quá hạn'),
            'res_model': 're.loan.note',
            'view_mode': 'list,form',
            'domain': [
                ('state', 'in', ('active', 'partial_paid')),
                ('date_maturity', '<', today),
                ('principal_outstanding', '>', 0),
            ],
        }

    def action_open_bg_outstanding(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Bảo lãnh outstanding'),
            'res_model': 're.bank.guarantee',
            'view_mode': 'list,form',
            'domain': [('state', 'in', ('issued', 'extended'))],
        }

    def action_open_bg_expiring(self):
        today = fields.Date.context_today(self)
        in_30d = today + timedelta(days=30)
        return {
            'type': 'ir.actions.act_window',
            'name': _('BL sắp hết hạn ≤30 ngày'),
            'res_model': 're.bank.guarantee',
            'view_mode': 'list,form',
            'domain': [
                ('state', 'in', ('issued', 'extended')),
                ('date_expiry', '>=', today),
                ('date_expiry', '<=', in_30d),
            ],
        }

    def action_open_bg_expired(self):
        today = fields.Date.context_today(self)
        return {
            'type': 'ir.actions.act_window',
            'name': _('⚠ BL hết hạn chưa gia hạn'),
            'res_model': 're.bank.guarantee',
            'view_mode': 'list,form',
            'domain': [
                ('state', 'in', ('issued', 'extended')),
                ('date_expiry', '<', today),
            ],
        }

    def action_refresh(self):
        """Tạo record mới = recompute toàn bộ KPI."""
        new_record = self.create({})
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': new_record.id,
            'view_mode': 'form',
            'view_id': self.env.ref(
                'rp_dashboard.view_rp_project_dashboard_form').id,
            'target': 'main',
        }
