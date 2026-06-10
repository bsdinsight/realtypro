# -*- coding: utf-8 -*-
"""Tests L6 — sinh account.move cho giải ngân / lãi / trả nợ."""
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 're_loan_account')
class TestJournalEntries(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        company = cls.env.company
        # Tạo các account.account cần thiết với account_type phù hợp
        Account = cls.env['account.account']
        cls.acc_loan = Account.create({
            'code': '3411X', 'name': 'TK Vay (test)',
            'account_type': 'liability_current'})
        cls.acc_bank = Account.create({
            'code': '1121X', 'name': 'Tiền gửi NH (test)',
            'account_type': 'asset_cash'})
        cls.acc_int_payable = Account.create({
            'code': '33531X', 'name': 'Lãi vay phải trả (test)',
            'account_type': 'liability_current'})
        cls.acc_int_expense = Account.create({
            'code': '635X', 'name': 'CP lãi vay (test)',
            'account_type': 'expense'})
        cls.acc_capitalized = Account.create({
            'code': '241X', 'name': 'XDCB dở dang (test)',
            'account_type': 'asset_non_current'})
        # Code phải unique per company → dùng prefix test riêng
        cls.journal = cls.env['account.journal'].create({
            'name': 'Loan Journal (test)', 'code': 'LOANT',
            'type': 'general'})
        # Map company defaults
        company.write({
            'loan_account_principal_id': cls.acc_loan.id,
            'loan_account_bank_id': cls.acc_bank.id,
            'loan_account_interest_payable_id': cls.acc_int_payable.id,
            'loan_account_interest_expense_id': cls.acc_int_expense.id,
            'loan_account_interest_capitalized_id': cls.acc_capitalized.id,
            'loan_journal_id': cls.journal.id,
        })
        # Loan setup
        cls.bank = cls.env['res.partner'].create({
            'name': 'NH-Acc', 'is_company': True, 'is_bank': True})
        cls.credit = cls.env['re.loan.credit.contract'].create({
            'name': 'HĐTD-ACC', 'partner_id': cls.bank.id,
            'amount_total': 10_000_000_000.0})
        cls.credit.action_activate()
        cls.facility = cls.env['re.loan.facility'].create({
            'name': 'F-ACC', 'credit_contract_id': cls.credit.id,
            'facility_type': 'revolving',
            'amount_limit': 10_000_000_000.0})
        cls.note = cls.env['re.loan.note'].create({
            'name': 'KW-ACC', 'facility_id': cls.facility.id,
            'amount': 1_000_000_000.0, 'date_note': '2026-01-01',
            'tenor_months': 12, 'interest_rate': 10.0})
        cls.note.action_activate()

    # ----- Disbursement post --------------------------------------------
    def test_disbursement_creates_move(self):
        d = self.env['re.loan.note.disbursement'].create({
            'note_id': self.note.id, 'date': '2026-01-02',
            'amount': 500_000_000.0})
        d.action_post_journal_entry()
        self.assertTrue(d.move_id)
        self.assertEqual(d.move_id.state, 'posted')
        self.assertTrue(d.is_posted)
        # 2 lines: bank debit + loan credit, balanced
        self.assertEqual(len(d.move_id.line_ids), 2)
        totals = sum(d.move_id.line_ids.mapped('debit')) \
            - sum(d.move_id.line_ids.mapped('credit'))
        self.assertEqual(totals, 0.0)

    def test_cannot_post_twice(self):
        d = self.env['re.loan.note.disbursement'].create({
            'note_id': self.note.id, 'amount': 100_000_000.0})
        d.action_post_journal_entry()
        with self.assertRaises(UserError):
            d.action_post_journal_entry()

    # ----- Repayment post -----------------------------------------------
    def test_repayment_principal_and_interest(self):
        self.env['re.loan.note.disbursement'].create({
            'note_id': self.note.id, 'amount': 1_000_000_000.0})
        r = self.env['re.loan.note.repayment'].create({
            'note_id': self.note.id, 'date': '2026-04-01',
            'amount_principal': 200_000_000.0,
            'amount_interest': 25_000_000.0})
        r.action_post_journal_entry()
        # 3 lines: loan debit + payable debit + bank credit
        self.assertEqual(len(r.move_id.line_ids), 3)
        bank_lines = r.move_id.line_ids.filtered(
            lambda l: l.account_id == self.acc_bank)
        self.assertEqual(sum(bank_lines.mapped('credit')), 225_000_000.0)

    # ----- Interest accrual: no capitalization (no bridge allocation) ---
    def test_interest_accrual_all_expense(self):
        # Note has interest_line_ids generated on activate
        line = self.note.interest_line_ids.sorted('period_no')[0]
        line.action_post_accrual()
        self.assertTrue(line.move_id)
        self.assertEqual(line.state, 'accrued')
        # Toàn bộ lãi vào TK 635 (no allocation → ratio = 0)
        self.assertEqual(line.capitalized_amount, 0.0)
        self.assertEqual(line.expense_amount, line.interest_amount)

    def test_interest_accrual_with_capitalization(self):
        # Bỏ qua test này nếu rp_loan_bridge không cài
        if 'allocation_ids' not in self.note._fields:
            self.skipTest("rp_loan_bridge not installed")
        # Tạo project + allocation 60% lãi capitalize
        proj = self.env['re.project'].create({
            'name': 'P-Cap', 'code': 'PCAP'})
        cat = self.env['rp.cost.category'].search([
            ('project_id', '=', proj.id),
            ('code', '=', '9.1')], limit=1)
        if not cat:
            self.skipTest("No cost cat 9.1 for project")
        self.env['rp.loan.allocation'].create({
            'note_id': self.note.id, 'project_id': proj.id,
            'cost_category_id': cat.id,
            'base': 'interest', 'method': 'percent', 'percent': 60.0})
        line = self.note.interest_line_ids.sorted('period_no')[1]
        line.action_post_accrual()
        # ~60% capitalize
        ratio = line.capitalized_amount / line.interest_amount
        self.assertGreater(ratio, 0.55)
        self.assertLess(ratio, 0.65)
