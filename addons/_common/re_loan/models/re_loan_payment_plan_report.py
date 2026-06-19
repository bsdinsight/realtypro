# -*- coding: utf-8 -*-
"""Báo cáo: Kế hoạch thanh toán khế ước theo năm.

UNION của 4 nguồn — TẤT CẢ đều lấy từ re.loan.note.interest.line
(tab "Lịch lãi"), KHÔNG dùng re.loan.note.repayment trực tiếp:
  - interest_line × principal × kế hoạch (kind='plan', pg='principal')
    = amount_principal_remaining (số gốc CÒN PHẢI TRẢ kỳ đó)
  - interest_line × interest × kế hoạch (kind='plan', pg='interest')
    = amount_interest_remaining (số lãi CÒN PHẢI TRẢ kỳ đó)
  - interest_line × principal × đã trả (kind='paid', pg='principal')
    = amount_principal_paid (gốc thực trả allocate vào kỳ đó)
  - interest_line × interest × đã trả (kind='paid', pg='interest')
    = amount_interest_paid (lãi thực trả allocate vào kỳ đó)

*** Tại sao dùng interest_line cho cả 4 nguồn ***
Các field paid trên interest_line đã được compute từ
`repayment_ids` allocate vào kỳ đó (xem
re_loan_note_interest_line._compute_paid_amounts). Dùng cùng nguồn
→ kế hoạch + đã trả nhất quán theo TỪNG KỲ, không bị lệch khi
repayment chưa allocate hoặc allocate cross-period.

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

                -- Đã trả - Tiền gốc (từ interest_line.amount_principal_paid)
                -- = Σ repayment.amount_principal allocate vào kỳ này
                SELECT
                  'il_p_paid'::varchar AS src,
                  il.id AS src_id,
                  il.note_id,
                  n.credit_contract_id,
                  n.facility_id,
                  n.partner_id,
                  date_trunc('month', il.date_to)::date
                    AS period_month,
                  to_char(il.date_to, 'YYYY') AS period_year,
                  'paid'::varchar AS kind,
                  'principal'::varchar AS pg_kind,
                  NULL::varchar AS period_state,
                  il.amount_principal_paid AS amount,
                  il.amount_principal_paid AS amount_principal,
                  0.0 AS amount_interest,
                  n.currency_id,
                  n.company_id
                FROM re_loan_note_interest_line il
                JOIN re_loan_note n ON n.id = il.note_id
                WHERE n.state NOT IN ('draft', 'cancelled')
                  AND il.amount_principal_paid > 0

                UNION ALL

                -- Đã trả - Tiền lãi (từ interest_line.amount_interest_paid)
                -- = Σ repayment.amount_interest allocate vào kỳ này
                SELECT
                  'il_i_paid'::varchar AS src,
                  il.id AS src_id,
                  il.note_id,
                  n.credit_contract_id,
                  n.facility_id,
                  n.partner_id,
                  date_trunc('month', il.date_to)::date
                    AS period_month,
                  to_char(il.date_to, 'YYYY') AS period_year,
                  'paid'::varchar AS kind,
                  'interest'::varchar AS pg_kind,
                  NULL::varchar AS period_state,
                  il.amount_interest_paid AS amount,
                  0.0 AS amount_principal,
                  il.amount_interest_paid AS amount_interest,
                  n.currency_id,
                  n.company_id
                FROM re_loan_note_interest_line il
                JOIN re_loan_note n ON n.id = il.note_id
                WHERE n.state NOT IN ('draft', 'cancelled')
                  AND il.amount_interest_paid > 0
              ) u
            )
        """)
