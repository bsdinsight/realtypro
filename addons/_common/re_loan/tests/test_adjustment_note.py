# -*- coding: utf-8 -*-
"""Việc 1436 — Thông báo Nợ/Có áp vào kỳ CÓ TIỀN GỐC.

Ca khách gặp: khế ước trả gốc cuối kỳ, bấm Áp dụng thông báo nợ vào
kỳ có tiền gốc > 0 thì nổ "Tổng tiền gốc theo lịch (30.000.000) vượt
số tiền khế ước (15.000.000)" — đúng gấp đôi.

Nguyên nhân: dòng "Điều chỉnh" mang CÙNG số kỳ với kỳ gốc, mà công
thức tiền gốc lại tính theo số kỳ, nên nó được gán lại nguyên tiền gốc
của kỳ đó. Dòng điều chỉnh là khoản truy thu / truy hoàn LÃI, không
bao giờ mang gốc.
"""
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 're_loan')
class TestAdjustmentNotePrincipal(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bank = cls.env['res.partner'].create({
            'name': 'NH 1436', 'is_company': True, 'is_bank': True})
        cls.contract = cls.env['re.loan.credit.contract'].create({
            'name': 'HĐTD-1436', 'partner_id': cls.bank.id,
            'amount_total': 1_000_000_000.0})
        cls.contract.action_activate()
        cls.facility = cls.env['re.loan.facility'].create({
            'name': 'F-1436', 'credit_contract_id': cls.contract.id,
            'facility_type': 'term', 'amount_limit': 1_000_000_000.0,
            'interest_rate_default': 10.0})

    def _note(self, plan='bullet', amount=15_000_000.0):
        note = self.env['re.loan.note'].create({
            'name': 'KU-1436-%s' % plan,
            'facility_id': self.facility.id,
            'amount': amount,
            'date_note': '2026-01-01',
            'tenor_months': 12,
            'interest_rate': 10.0,
            'repayment_plan': plan,
        })
        note.action_activate()
        return note

    def _apply(self, note, line):
        adj = self.env['re.loan.adjustment.note'].create({
            'name': '525345',
            'kind': 'debit',
            'note_id': note.id,
            'amount': 400_000.0,
            'date_issue': '2026-10-08',
            'target_interest_line_id': line.id,
        })
        adj.action_apply()
        return adj

    def _periods(self, note):
        return note.interest_line_ids.filtered(
            lambda l: l.line_type == 'period').sorted('period_no')

    # ----- Ca khách báo -------------------------------------------------
    def test_apply_on_period_carrying_principal(self):
        """Trả gốc cuối kỳ: kỳ cuối mang TRỌN gốc — đúng ca nổ lỗi."""
        note = self._note(plan='bullet')
        last = self._periods(note)[-1]
        self.assertEqual(last.principal_due, 15_000_000.0,
                         'dựng sai: kỳ cuối phải mang trọn gốc')
        adj = self._apply(note, last)
        self.assertEqual(adj.state, 'applied')
        self.assertEqual(adj.adjustment_line_id.principal_due, 0.0,
                         'dòng điều chỉnh KHÔNG được mang tiền gốc')
        self.assertAlmostEqual(
            sum(note.interest_line_ids.mapped('principal_due')),
            15_000_000.0, delta=1,
            msg='tổng gốc theo lịch phải đúng bằng số tiền khế ước')

    def test_apply_on_equal_principal_plan(self):
        """Trả gốc đều: MỌI kỳ đều có gốc > 0 nên kỳ nào cũng từng nổ."""
        note = self._note(plan='equal_principal', amount=12_000_000.0)
        first = self._periods(note)[0]
        self.assertGreater(first.principal_due, 0)
        self._apply(note, first)
        self.assertAlmostEqual(
            sum(note.interest_line_ids.mapped('principal_due')),
            12_000_000.0, delta=1)

    # ----- Phần việc của thông báo vẫn phải chạy đúng --------------------
    def test_adjustment_carries_the_interest(self):
        note = self._note(plan='bullet')
        last = self._periods(note)[-1]
        adj = self._apply(note, last)
        adj_line = adj.adjustment_line_id
        self.assertEqual(adj_line.line_type, 'adjustment')
        self.assertEqual(adj_line.period_no, last.period_no)
        self.assertAlmostEqual(adj_line.interest_amount, 400_000.0,
                               delta=1, msg='truy thu phải cộng lãi')

    def test_credit_note_subtracts(self):
        note = self._note(plan='bullet')
        last = self._periods(note)[-1]
        adj = self.env['re.loan.adjustment.note'].create({
            'name': '525346', 'kind': 'credit', 'note_id': note.id,
            'amount': 400_000.0, 'date_issue': '2026-10-08',
            'target_interest_line_id': last.id,
        })
        adj.action_apply()
        self.assertAlmostEqual(
            adj.adjustment_line_id.interest_amount, -400_000.0, delta=1)
        self.assertEqual(adj.adjustment_line_id.principal_due, 0.0)

    def test_recompute_keeps_adjustment_principal_zero(self):
        """Đổi số tiền khế ước thì lịch tính lại — dòng điều chỉnh vẫn
        phải ở 0, không ăn theo công thức của kỳ."""
        note = self._note(plan='bullet')
        last = self._periods(note)[-1]
        adj = self._apply(note, last)
        note.amount = 20_000_000.0
        adj.adjustment_line_id.invalidate_recordset()
        self.assertEqual(adj.adjustment_line_id.principal_due, 0.0)
        self.assertAlmostEqual(
            sum(note.interest_line_ids.mapped('principal_due')),
            20_000_000.0, delta=1)
