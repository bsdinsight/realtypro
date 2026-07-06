# -*- coding: utf-8 -*-
"""KPI thuê tài chính trên dashboard Quản lý Vay (tham khảo)."""
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models


class ReLoanDashboard(models.TransientModel):
    _inherit = 're.loan.dashboard'

    kpi_lease_debt = fields.Monetary(
        string='Dư nợ gốc thuê tài chính',
        help='Σ dư nợ gốc các HĐ ĐI THUÊ tài chính đang hiệu lực '
             '(app Thuê tài sản) — nghĩa vụ tín dụng ngoài vay NH.')
    kpi_lease_due_30d = fields.Monetary(
        string='Kỳ thuê đến hạn ≤30 ngày',
        help='Σ các kỳ thuê (đi thuê) chưa thanh toán đến hạn trong '
             '30 ngày tới.')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        today = fields.Date.context_today(self)
        fin_in = self.env['re.lease.contract'].search([
            ('state', '=', 'active'), ('direction', '=', 'in'),
            ('lease_type', '=', 'finance')])
        res['kpi_lease_debt'] = sum(
            fin_in.mapped('outstanding_principal'))
        due = self.env['re.lease.payment.line'].search([
            ('contract_id.state', '=', 'active'),
            ('direction', '=', 'in'),
            ('state', '!=', 'paid'),
            ('date_due', '<=', today + relativedelta(days=30))])
        res['kpi_lease_due_30d'] = sum(due.mapped('amount_total'))
        return res

    def action_open_lease_contracts(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'HĐ đi thuê tài chính',
            'res_model': 're.lease.contract',
            'view_mode': 'list,form',
            'domain': [('direction', '=', 'in'),
                       ('lease_type', '=', 'finance')],
            'context': {'search_default_f_active': 1},
        }
