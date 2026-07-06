# -*- coding: utf-8 -*-
"""Dashboard Thuê tài sản — KPI 2×2 + dư nợ/phải thu thuê TC + kỳ đến
hạn + chênh lệch back-to-back. SVG server-side."""
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models

from . import lease_svg


class ReLeaseDashboard(models.TransientModel):
    _name = 're.lease.dashboard'
    _description = 'Thuê tài sản — Dashboard'

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = 'Thuê tài sản — Dashboard'

    kpi_active_total = fields.Integer(string='HĐ hiệu lực')
    kpi_debt_finance_in = fields.Monetary(
        string='Dư nợ gốc thuê TC (đi thuê)')
    kpi_receivable_finance_out = fields.Monetary(
        string='Phải thu thuê TC (cho thuê lại)')
    kpi_due_30d_in = fields.Monetary(
        string='Phải trả 30 ngày tới')
    kpi_due_30d_out = fields.Monetary(
        string='Phải thu 30 ngày tới')
    kpi_sublease_margin = fields.Monetary(
        string='Chênh lệch cho thuê lại (lũy kế)')
    kpi_deposit_total = fields.Monetary(string='Tổng ký cược')

    chart_matrix_html = fields.Html(sanitize=False)
    chart_debt_by_partner_html = fields.Html(sanitize=False)
    chart_due_html = fields.Html(sanitize=False)

    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        Contract = self.env['re.lease.contract']
        Line = self.env['re.lease.payment.line']
        today = fields.Date.context_today(self)
        active = Contract.search([('state', '=', 'active')])

        res['kpi_active_total'] = len(active)
        counts = {}
        for c in active:
            key = (c.direction, c.lease_type)
            counts[key] = counts.get(key, 0) + 1
        fin_in = active.filtered(
            lambda c: c.direction == 'in' and c.lease_type == 'finance')
        fin_out = active.filtered(
            lambda c: c.direction == 'out' and c.lease_type == 'finance')
        res['kpi_debt_finance_in'] = sum(
            fin_in.mapped('outstanding_principal'))
        res['kpi_receivable_finance_out'] = sum(
            fin_out.mapped('outstanding_principal'))
        res['kpi_deposit_total'] = sum(active.mapped('deposit'))
        res['kpi_sublease_margin'] = sum(
            active.filtered('child_lease_ids').mapped('sublease_margin'))

        due30 = Line.search([
            ('contract_id.state', '=', 'active'),
            ('state', '!=', 'paid'),
            ('date_due', '<=', today + relativedelta(days=30)),
        ])
        res['kpi_due_30d_in'] = sum(
            due30.filtered(lambda l: l.direction == 'in')
            .mapped('amount_total'))
        res['kpi_due_30d_out'] = sum(
            due30.filtered(lambda l: l.direction == 'out')
            .mapped('amount_total'))

        res['chart_matrix_html'] = lease_svg.matrix_2x2(counts)
        # Dư nợ thuê TC theo đối tác (top 8)
        by_partner = {}
        for c in fin_in:
            by_partner[c.partner_id.name] = (
                by_partner.get(c.partner_id.name, 0.0)
                + c.outstanding_principal)
        top = sorted(by_partner.items(), key=lambda kv: -kv[1])[:8]
        res['chart_debt_by_partner_html'] = lease_svg.hbar(top)
        # Kỳ đến hạn 6 tháng tới (mọi chiều, chưa trả)
        months = []
        for k in range(6):
            m0 = (today + relativedelta(months=k)).replace(day=1)
            m1 = m0 + relativedelta(months=1)
            lines = Line.search([
                ('contract_id.state', '=', 'active'),
                ('state', '!=', 'paid'),
                ('date_due', '>=', m0), ('date_due', '<', m1)])
            months.append(('T%d' % m0.month,
                           sum(lines.mapped('amount_total'))))
        res['chart_due_html'] = lease_svg.vbar(months)
        return res

    def action_open_contracts(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Hợp đồng thuê',
            'res_model': 're.lease.contract',
            'view_mode': 'list,form',
            'context': {'search_default_f_active': 1},
        }

    def action_open_due_lines(self):
        today = fields.Date.context_today(self)
        return {
            'type': 'ir.actions.act_window',
            'name': 'Kỳ đến hạn 30 ngày',
            'res_model': 're.lease.payment.line',
            'view_mode': 'list',
            'domain': [
                ('contract_id.state', '=', 'active'),
                ('state', '!=', 'paid'),
                ('date_due', '<=', today + relativedelta(days=30))],
        }
