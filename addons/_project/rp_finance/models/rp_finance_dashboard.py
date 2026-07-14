# -*- coding: utf-8 -*-
"""Dashboard Tài chính — KPI dòng tiền dự án + drill-down.

Pattern giống rp_dashboard (rp.project.dashboard): TransientModel,
mỗi lần mở menu tạo record mới, default_get() query realtime.
Nhấp menu "Tài chính" trên navbar → menu con seq nhỏ nhất là
Dashboard nên dashboard mở ngay.
"""
from odoo import api, fields, models


class RpFinanceDashboard(models.TransientModel):
    _name = 'rp.finance.dashboard'
    _description = 'Realty Project — Dashboard Tài chính'

    @api.depends_context('lang')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = 'Tài chính — Dashboard'

    # ─── 1. Kế hoạch chi phí ───────────────────────────────────────
    kpi_estimate_total = fields.Monetary(
        string='Tổng khái toán',
        help='Σ amount của rp.structure.estimate.line (mọi dự án active).')
    kpi_boq_total = fields.Monetary(
        string='Tổng dự toán (BOQ)',
        help='Σ amount của rp.boq.line.')
    kpi_contract_value = fields.Monetary(
        string='Giá trị HĐ đã ký',
        help='Σ contract_value_total của rp.contract '
             'state ∈ {signed, executing, completed}.')

    # ─── 2. Thực hiện ─────────────────────────────────────────────
    kpi_acceptance_to_date = fields.Monetary(
        string='Nghiệm thu lũy kế',
        help='Σ acceptance_value_to_date của HĐ đã ký (BBN approved).')
    kpi_advance_open = fields.Monetary(
        string='Tạm ứng chưa cấn trừ',
        help='Σ amount_remaining của Tạm ứng state ∈ '
             '{approved, partial_paid, paid}.')
    kpi_advance_to_approve = fields.Integer(
        string='Tạm ứng chờ duyệt',
        help='Số phiếu tạm ứng state = to_approve.')

    # ─── 3. Thanh toán ────────────────────────────────────────────
    kpi_invoice_total = fields.Monetary(
        string='Hoá đơn NT đã ghi nhận',
        help='Σ amount_total hoá đơn nhà thầu (in_invoice, posted) '
             'gắn mốc thanh toán HĐ.')
    kpi_invoice_residual = fields.Monetary(
        string='Còn phải trả (hoá đơn)',
        help='Σ amount_residual của các hoá đơn trên.')
    kpi_milestone_due_30d = fields.Integer(
        string='Mốc TT đến hạn ≤30 ngày',
        help='Mốc thanh toán chưa trả có due_date trong 30 ngày tới '
             '(kể cả quá hạn).')
    kpi_milestone_paid = fields.Monetary(
        string='Đã thanh toán (theo mốc)',
        help='Σ amount mốc thanh toán state = paid.')

    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id)

    # ------------------------------------------------------------------
    # Compute
    # ------------------------------------------------------------------
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        res.update(self._compute_kpis())
        return res

    @api.model
    def _compute_kpis(self):
        Est = self.env['rp.structure.estimate.line']
        Boq = self.env['rp.boq.line']
        Contract = self.env['rp.contract']
        Advance = self.env['rp.advance.payment']
        Milestone = self.env['rp.contract.payment.milestone']
        Move = self.env['account.move']

        signed = Contract.search(
            [('state', 'in', ('signed', 'executing', 'completed'))])

        advances_open = Advance.search(
            [('state', 'in', ('approved', 'partial_paid', 'paid'))])

        bills = Move.search([
            ('move_type', '=', 'in_invoice'),
            ('state', '=', 'posted'),
            ('payment_milestone_id', '!=', False),
        ])

        today = fields.Date.context_today(self)
        due_soon = Milestone.search_count([
            ('state', '!=', 'paid'),
            ('due_date', '!=', False),
            ('due_date', '<=', fields.Date.add(today, days=30)),
        ])
        paid = self.env['rp.contract.payment.milestone'].search(
            [('state', '=', 'paid')])

        return {
            'kpi_estimate_total': sum(
                Est.search([]).mapped('amount')),
            'kpi_boq_total': sum(Boq.search([]).mapped('amount')),
            'kpi_contract_value': sum(signed.mapped('contract_value_total')),
            'kpi_acceptance_to_date': sum(
                signed.mapped('acceptance_value_to_date')),
            'kpi_advance_open': sum(advances_open.mapped('amount_remaining')),
            'kpi_advance_to_approve': Advance.search_count(
                [('state', '=', 'to_approve')]),
            'kpi_invoice_total': sum(bills.mapped('amount_total')),
            'kpi_invoice_residual': sum(bills.mapped('amount_residual')),
            'kpi_milestone_due_30d': due_soon,
            'kpi_milestone_paid': sum(paid.mapped('amount')),
        }

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_refresh(self):
        self.write(self._compute_kpis())
        return True

    def _open(self, name, res_model, domain=None, views='list,form',
              context=None):
        return {
            'type': 'ir.actions.act_window',
            'name': name,
            'res_model': res_model,
            'view_mode': views,
            'domain': domain or [],
            'context': context or {},
            'target': 'current',
        }

    def action_open_estimate(self):
        act = self.env['ir.actions.act_window']._for_xml_id(
            'rp_cost_base.action_rp_structure_estimate_summary')
        return act

    def action_open_boq(self):
        act = self.env['ir.actions.act_window']._for_xml_id(
            'rp_finance.action_rp_finance_boq')
        return act

    def action_open_contracts(self):
        return self._open(
            'HĐ nhà thầu đã ký', 'rp.contract',
            [('state', 'in', ('signed', 'executing', 'completed'))])

    def action_open_advances(self):
        return self._open(
            'Tạm ứng chờ duyệt', 'rp.advance.payment',
            [('state', '=', 'to_approve')])

    def action_open_bills(self):
        return self._open(
            'Hoá đơn nhà thầu', 'account.move',
            [('move_type', '=', 'in_invoice'), ('state', '=', 'posted'),
             ('payment_milestone_id', '!=', False)],
            context={'default_move_type': 'in_invoice'})

    def action_open_milestones_due(self):
        today = fields.Date.context_today(self)
        return self._open(
            'Mốc thanh toán đến hạn ≤30 ngày',
            'rp.contract.payment.milestone',
            [('state', '!=', 'paid'), ('due_date', '!=', False),
             ('due_date', '<=', fields.Date.add(today, days=30))])
