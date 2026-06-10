# -*- coding: utf-8 -*-
"""Báo cáo: Kế hoạch thanh toán khế ước theo năm.

UNION của 2 nguồn:
  - re.loan.note.interest.line: kế hoạch trả (gốc + lãi) — kind='plan'
  - re.loan.note.repayment:     đã trả thực tế (gốc + lãi) — kind='paid'

Pivot: row=HĐTD/KW, col=tháng × {kế hoạch, đã trả}, measure=amount.
"""
from odoo import fields, models, tools


class ReLoanPaymentPlanReport(models.Model):
    _name = 're.loan.payment.plan.report'
    _description = 'Báo cáo kế hoạch thanh toán KW theo năm'
    _auto = False
    _order = 'credit_contract_id, note_id, period_month, kind'

    note_id = fields.Many2one(
        're.loan.note', string='Khế ước', readonly=True)
    credit_contract_id = fields.Many2one(
        're.loan.credit.contract', string='HĐTD', readonly=True)
    facility_id = fields.Many2one(
        're.loan.facility', string='Hạn mức', readonly=True)
    partner_id = fields.Many2one(
        'res.partner', string='Ngân hàng', readonly=True)
    period_month = fields.Date(
        string='Tháng', readonly=True,
        help='Tháng đến hạn (kế hoạch) hoặc tháng trả (thực tế).')
    period_year = fields.Char(
        string='Năm', readonly=True)
    kind = fields.Selection(
        [('plan', 'Kế hoạch'),
         ('paid', 'Đã trả')],
        string='Loại', readonly=True)
    amount = fields.Monetary(
        string='Số tiền', readonly=True)
    amount_principal = fields.Monetary(
        string='Gốc', readonly=True)
    amount_interest = fields.Monetary(
        string='Lãi', readonly=True)
    currency_id = fields.Many2one(
        'res.currency', readonly=True)
    company_id = fields.Many2one(
        'res.company', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self._cr, self._table)
        self._cr.execute(f"""
            CREATE OR REPLACE VIEW {self._table} AS (
              SELECT ROW_NUMBER() OVER
                       (ORDER BY src, src_id) AS id, *
              FROM (
                -- Kế hoạch: từ lịch lãi/gốc
                SELECT
                  'il'::varchar AS src,
                  il.id AS src_id,
                  il.note_id,
                  n.credit_contract_id,
                  n.facility_id,
                  n.partner_id,
                  date_trunc('month', il.date_to)::date
                    AS period_month,
                  to_char(il.date_to, 'YYYY') AS period_year,
                  'plan'::varchar AS kind,
                  il.total_due AS amount,
                  il.principal_due AS amount_principal,
                  il.interest_amount AS amount_interest,
                  n.currency_id,
                  n.company_id
                FROM re_loan_note_interest_line il
                JOIN re_loan_note n ON n.id = il.note_id
                WHERE n.state NOT IN ('draft', 'cancelled')

                UNION ALL

                -- Đã trả: từ trả nợ thực tế
                SELECT
                  'rp'::varchar AS src,
                  r.id AS src_id,
                  r.note_id,
                  n.credit_contract_id,
                  n.facility_id,
                  n.partner_id,
                  date_trunc('month', r.date)::date AS period_month,
                  to_char(r.date, 'YYYY') AS period_year,
                  'paid'::varchar AS kind,
                  r.amount_total AS amount,
                  r.amount_principal,
                  r.amount_interest,
                  n.currency_id,
                  n.company_id
                FROM re_loan_note_repayment r
                JOIN re_loan_note n ON n.id = r.note_id
              ) u
            )
        """)
