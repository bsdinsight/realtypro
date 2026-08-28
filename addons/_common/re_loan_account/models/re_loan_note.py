# -*- coding: utf-8 -*-
"""Helper: resolve loan accounts theo thứ tự facility → company."""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ReLoanNote(models.Model):
    _inherit = 're.loan.note'

    # ------------------------------------------------------------------
    # Bút toán liên quan (account.move) — Báo cáo (1) Bảng kê chứng từ
    # ------------------------------------------------------------------
    move_ids = fields.One2many(
        'account.move', 'loan_note_id', string='Bút toán kế toán')
    move_count = fields.Integer(
        string='Số chứng từ', compute='_compute_move_count')

    @api.depends('move_ids')
    def _compute_move_count(self):
        for rec in self:
            rec.move_count = len(rec.move_ids)

    def action_view_moves(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Chứng từ KW %s', self.name),
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('loan_note_id', '=', self.id)],
            'context': {'default_loan_note_id': self.id},
        }

    # ------------------------------------------------------------------
    # Đối chiếu Loan-side vs Accounting-side (Báo cáo 2)
    # ------------------------------------------------------------------
    accounting_outstanding = fields.Monetary(
        string='Dư nợ kế toán', compute='_compute_reconciliation',
        help='Số dư phía kế toán = Σ Có − Σ Nợ trên TK Vay (TK 3411) '
             'filtered theo KW.')
    outstanding_variance = fields.Monetary(
        string='Chênh lệch (Loan − KT)', compute='_compute_reconciliation',
        help='Dư nợ gốc (loan) − Dư nợ kế toán. Khác 0 = bút toán chưa '
             'post đủ hoặc lệch.')

    @api.depends('move_ids', 'principal_outstanding', 'facility_id',
                 'company_id.loan_account_principal_id')
    def _compute_reconciliation(self):
        AML = self.env['account.move.line']
        for rec in self:
            loan_acc = (rec.facility_id.loan_account_principal_id
                        or rec.company_id.loan_account_principal_id)
            if not loan_acc:
                rec.accounting_outstanding = 0.0
                rec.outstanding_variance = rec.principal_outstanding
                continue
            lines = AML.search([
                ('loan_note_id', '=', rec.id),
                ('account_id', '=', loan_acc.id),
                ('parent_state', '=', 'posted'),
            ])
            # Loan = LIABILITY: credit tăng nợ, debit giảm nợ.
            acc_out = (sum(lines.mapped('credit'))
                       - sum(lines.mapped('debit')))
            rec.accounting_outstanding = acc_out
            rec.outstanding_variance = rec.principal_outstanding - acc_out

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------
    def _get_loan_account(self, fname):
        """Lấy account.account theo `fname` từ facility (override) hoặc
        từ company.  fname là tên field, vd
        'loan_account_principal_id'."""
        self.ensure_one()
        facility_account = (
            self.facility_id and getattr(self.facility_id, fname, False))
        if facility_account:
            return facility_account
        company_account = getattr(self.company_id, fname, False)
        if not company_account:
            raise UserError(_(
                "Chưa cấu hình tài khoản '%(f)s' cho company "
                "'%(c)s'. Vào Settings → Loan Accounts để map.",
                f=fname, c=self.company_id.name))
        return company_account

    def _get_loan_journal(self):
        self.ensure_one()
        journal = (self.facility_id and self.facility_id.loan_journal_id) \
            or self.company_id.loan_journal_id
        if not journal:
            raise UserError(_(
                "Chưa cấu hình Sổ Nhật ký Vay cho company '%s'.",
                self.company_id.name))
        return journal

    # ------------------------------------------------------------------
    # Quy đổi ngoại tệ khi ghi sổ
    # ------------------------------------------------------------------
    # SỔ CÁI LUÔN GHI BẰNG ĐỒNG TIỀN HẠCH TOÁN CỦA CÔNG TY.
    #
    # Trước đây ba chỗ post bút toán (giải ngân / lãi / trả nợ) đưa
    # THẲNG số tiền của khế ước vào cột debit-credit. Với khế ước VND
    # thì đúng, vì hai đồng tiền trùng nhau. Với khế ước USD thì con số
    # USD nằm trong sổ cái dưới nhãn VND — sai gấp hơn hai vạn lần và
    # không có gì báo động, vì bút toán vẫn cân.
    #
    # Không ai gặp lỗi này chỉ vì chưa có khế ước ngoại tệ nào. Đánh giá
    # lại tỷ giá (TT 200 Điều 69) là nghiệp vụ đầu tiên bắt buộc phải có
    # khế ước ngoại tệ, nên phải vá nền trước khi xây nó.
    def _fx(self, amount, date):
        """Quy đổi số tiền của KW sang đồng tiền hạch toán.

        Trả về `(số tiền ghi sổ, số tiền nguyên tệ, id đồng tiền)`.
        Id đồng tiền là False khi KW cùng đồng tiền với công ty — khi đó
        KHÔNG gắn currency_id vào dòng bút toán, giữ nguyên hành vi cũ.
        """
        self.ensure_one()
        comp_cur = self.company_id.currency_id
        cur = self.currency_id or comp_cur
        if cur == comp_cur:
            return comp_cur.round(amount), 0.0, False
        return (cur._convert(amount, comp_cur, self.company_id,
                             date or fields.Date.context_today(self)),
                amount, cur.id)

    def _fx_line(self, account, label, amount, date, debit=True):
        """Một dòng bút toán đã quy đổi, kèm nguyên tệ để còn đối chiếu."""
        self.ensure_one()
        book, fc, cur_id = self._fx(amount, date)
        vals = {
            'account_id': account.id,
            'name': label,
            'debit': book if debit else 0.0,
            'credit': 0.0 if debit else book,
            'partner_id': self.partner_id.id or False,
        }
        if cur_id:
            vals['currency_id'] = cur_id
            vals['amount_currency'] = fc if debit else -fc
        return (0, 0, vals)

    def _fx_balance_line(self, account, label, others, date, debit=False):
        """Dòng đối ứng lấy ĐÚNG tổng các dòng kia, không quy đổi lại.

        Quy đổi riêng từng vế rồi cộng lại có thể lệch một đồng do làm
        tròn, và Odoo sẽ chặn bút toán không cân. Nên vế đối ứng luôn
        bằng tổng vế bên kia thay vì tự tính lại từ số nguyên tệ.
        """
        self.ensure_one()
        book = sum(l[2].get('debit', 0.0) + l[2].get('credit', 0.0)
                   for l in others)
        fc = sum(abs(l[2].get('amount_currency', 0.0)) for l in others)
        vals = {
            'account_id': account.id,
            'name': label,
            'debit': book if debit else 0.0,
            'credit': 0.0 if debit else book,
            'partner_id': self.partner_id.id or False,
        }
        if self.currency_id and self.currency_id != self.company_id.currency_id:
            vals['currency_id'] = self.currency_id.id
            vals['amount_currency'] = fc if debit else -fc
        return (0, 0, vals)

    # ------------------------------------------------------------------
    # Capitalization helper
    # ------------------------------------------------------------------
    def _capitalization_ratio(self):
        """Tỷ lệ lãi vay capitalize (0..1).

        Đọc từ rp.loan.allocation (bridge L5) nếu cài: tổng
        amount_allocated của các allocation interest có cost_category
        set / interest_total_planned. Nếu bridge không cài → 0.
        """
        self.ensure_one()
        if 'allocation_ids' not in self._fields:
            return 0.0
        total_planned = self.interest_total_planned or 0.0
        if not total_planned:
            return 0.0
        capitalized = 0.0
        for a in self.allocation_ids:
            if a.base in ('interest', 'both') and a.cost_category_id:
                # 'both' đóng góp 50% interest theo allocation_total compute
                share = a.amount_allocated * (
                    0.5 if a.base == 'both' else 1.0)
                capitalized += share
        ratio = capitalized / total_planned
        return min(max(ratio, 0.0), 1.0)
