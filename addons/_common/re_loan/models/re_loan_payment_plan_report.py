# -*- coding: utf-8 -*-
"""Báo cáo: Kế hoạch thanh toán khế ước theo năm.

UNION của 4 nguồn (mỗi kỳ tách thành 2 dòng gốc + lãi):
  - re.loan.note.interest.line × {principal, interest}: kế hoạch
    trả → kind='plan', pg_kind='principal' / 'interest'
    *** SEMANTIC: "Kế hoạch" = số CÒN PHẢI TRẢ (= due - đã trả),
        KHÔNG phải tổng due full. Lấy từ field
        amount_principal_remaining + amount_interest_remaining. ***
  - re.loan.note.repayment × {principal, interest}: đã trả thực tế
    → kind='paid', pg_kind='principal' / 'interest'

Pivot: row = HĐTD → KW → pg_kind (gốc/lãi), col = tháng × {kế hoạch,
đã trả}, measure = amount.

Status (period_state) lấy từ interest_line.state — cho phép filter
kỳ chưa thanh toán / quá hạn / một phần / đủ.
"""
from odoo import fields, models, tools


class ReLoanPaymentPlanReport(models.Model):
    _name = 're.loan.payment.plan.report'
    _description = 'Báo cáo kế hoạch thanh toán KW theo năm'
    _auto = False
    _order = 'credit_contract_id, note_id, period_month, kind, pg_kind'

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
        string='Loại', readonly=True,
        help='Kế hoạch = số CÒN phải trả tháng đó (= due - đã trả). '
             'Khi đã trả đủ kỳ → kế hoạch = 0 (row không xuất hiện). '
             'Đã trả = số thực tế đã trả từ trả nợ thực tế.')
    pg_kind = fields.Selection(
        [('principal', 'Tiền gốc'),
         ('interest',  'Tiền lãi')],
        string='Gốc/Lãi', readonly=True,
        help='Tách dòng gốc/lãi → pivot xem riêng từng cấu phần.')
    period_state = fields.Selection(
        [('planned',      'Dự kiến'),
         ('accrued',      'Đã ghi nhận'),
         ('partial_paid', 'Trả một phần'),
         ('paid',         'Đã trả đủ')],
        string='Trạng thái kỳ', readonly=True,
        help='Trạng thái kỳ lãi/gốc (chỉ cho dòng kế hoạch). '
             'Dòng đã trả → trống.')
    amount = fields.Monetary(
        string='Số tiền', readonly=True)
    amount_principal = fields.Monetary(
        string='Gốc', readonly=True,
        help='Backward compat — số tiền gốc của row này. = amount '
             'khi pg_kind=principal, = 0 khi pg_kind=interest.')
    amount_interest = fields.Monetary(
        string='Lãi', readonly=True,
        help='Backward compat — số tiền lãi của row này. = amount '
             'khi pg_kind=interest, = 0 khi pg_kind=principal.')
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
                -- Kế hoạch - Tiền gốc CÒN PHẢI TRẢ (= due - đã trả)
                SELECT
                  'il_p'::varchar AS src,
                  il.id AS src_id,
                  il.note_id,
                  n.credit_contract_id,
                  n.facility_id,
                  n.partner_id,
                  date_trunc('month', il.date_to)::date
                    AS period_month,
                  to_char(il.date_to, 'YYYY') AS period_year,
                  'plan'::varchar AS kind,
                  'principal'::varchar AS pg_kind,
                  il.state::varchar AS period_state,
                  il.amount_principal_remaining AS amount,
                  il.amount_principal_remaining AS amount_principal,
                  0.0 AS amount_interest,
                  n.currency_id,
                  n.company_id
                FROM re_loan_note_interest_line il
                JOIN re_loan_note n ON n.id = il.note_id
                WHERE n.state NOT IN ('draft', 'cancelled')
                  AND il.amount_principal_remaining > 0

                UNION ALL

                -- Kế hoạch - Tiền lãi CÒN PHẢI TRẢ (= due - đã trả)
                SELECT
                  'il_i'::varchar AS src,
                  il.id AS src_id,
                  il.note_id,
                  n.credit_contract_id,
                  n.facility_id,
                  n.partner_id,
                  date_trunc('month', il.date_to)::date
                    AS period_month,
                  to_char(il.date_to, 'YYYY') AS period_year,
                  'plan'::varchar AS kind,
                  'interest'::varchar AS pg_kind,
                  il.state::varchar AS period_state,
                  il.amount_interest_remaining AS amount,
                  0.0 AS amount_principal,
                  il.amount_interest_remaining AS amount_interest,
                  n.currency_id,
                  n.company_id
                FROM re_loan_note_interest_line il
                JOIN re_loan_note n ON n.id = il.note_id
                WHERE n.state NOT IN ('draft', 'cancelled')
                  AND il.amount_interest_remaining > 0

                UNION ALL

                -- Đã trả - Tiền gốc (từ trả nợ thực tế)
                SELECT
                  'rp_p'::varchar AS src,
                  r.id AS src_id,
                  r.note_id,
                  n.credit_contract_id,
                  n.facility_id,
                  n.partner_id,
                  date_trunc('month', r.date)::date AS period_month,
                  to_char(r.date, 'YYYY') AS period_year,
                  'paid'::varchar AS kind,
                  'principal'::varchar AS pg_kind,
                  NULL::varchar AS period_state,
                  r.amount_principal AS amount,
                  r.amount_principal,
                  0.0 AS amount_interest,
                  n.currency_id,
                  n.company_id
                FROM re_loan_note_repayment r
                JOIN re_loan_note n ON n.id = r.note_id
                WHERE r.amount_principal > 0

                UNION ALL

                -- Đã trả - Tiền lãi (từ trả nợ thực tế)
                SELECT
                  'rp_i'::varchar AS src,
                  r.id AS src_id,
                  r.note_id,
                  n.credit_contract_id,
                  n.facility_id,
                  n.partner_id,
                  date_trunc('month', r.date)::date AS period_month,
                  to_char(r.date, 'YYYY') AS period_year,
                  'paid'::varchar AS kind,
                  'interest'::varchar AS pg_kind,
                  NULL::varchar AS period_state,
                  r.amount_interest AS amount,
                  0.0 AS amount_principal,
                  r.amount_interest,
                  n.currency_id,
                  n.company_id
                FROM re_loan_note_repayment r
                JOIN re_loan_note n ON n.id = r.note_id
                WHERE r.amount_interest > 0
              ) u
            )
        """)
