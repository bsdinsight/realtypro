# -*- coding: utf-8 -*-
"""
Tests L2c — cron quá hạn + nhắc đáo hạn + aging bucket.
"""
from datetime import date, timedelta

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 're_loan')
class TestCronAging(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bank = cls.env['res.partner'].create({
            'name': 'NH Cron', 'is_company': True, 'is_bank': True})
        cls.contract = cls.env['re.loan.credit.contract'].create({
            'name': 'HĐTD-CRON', 'partner_id': cls.bank.id,
            'amount_total': 10_000_000_000.0})
        cls.contract.action_activate()
        cls.fac = cls.env['re.loan.facility'].create({
            'name': 'F-cron', 'credit_contract_id': cls.contract.id,
            'facility_type': 'revolving', 'amount_limit': 10_000_000_000.0,
            'interest_rate_default': 10.0})

    def _active_note(self, maturity, amount=1_000_000_000.0, disb=True):
        note = self.env['re.loan.note'].create({
            'name': 'KW-%s' % maturity, 'facility_id': self.fac.id,
            'amount': amount, 'date_note': '2020-01-01',
            'date_maturity': maturity, 'interest_rate': 10.0})
        note.action_activate()
        if disb:
            self.env['re.loan.note.disbursement'].create({
                'note_id': note.id, 'amount': amount, 'date': '2020-01-02'})
        return note

    # ----- Cron overdue ---------------------------------------------------
    def test_cron_marks_overdue(self):
        note = self._active_note('2020-12-31')  # quá khứ
        self.assertEqual(note.state, 'active')
        self.env['re.loan.note']._cron_update_loan_status()
        self.assertEqual(note.state, 'overdue')

    def test_cron_not_overdue_future(self):
        future = (date.today() + timedelta(days=365)).strftime('%Y-%m-%d')
        note = self._active_note(future)
        self.env['re.loan.note']._cron_update_loan_status()
        self.assertEqual(note.state, 'active')

    def test_cron_recovers_when_paid(self):
        note = self._active_note('2020-12-31')
        self.env['re.loan.note']._cron_update_loan_status()
        self.assertEqual(note.state, 'overdue')
        # trả hết → cron đưa về fully_paid
        self.env['re.loan.note.repayment'].create({
            'note_id': note.id, 'amount_principal': 1_000_000_000.0,
            'date': '2021-01-01'})
        # repayment đã gọi _update_payment_state → fully_paid ngay
        self.assertEqual(note.state, 'fully_paid')

    # ----- Aging bucket ---------------------------------------------------
    def test_aging_current_for_future(self):
        future = (date.today() + timedelta(days=100)).strftime('%Y-%m-%d')
        note = self._active_note(future)
        self.assertEqual(note.aging_bucket, 'current')

    def test_aging_bucket_overdue(self):
        past = (date.today() - timedelta(days=45)).strftime('%Y-%m-%d')
        note = self._active_note(past)
        self.assertEqual(note.aging_bucket, 'b31_60')

    def test_aging_bucket_long_overdue(self):
        past = (date.today() - timedelta(days=400)).strftime('%Y-%m-%d')
        note = self._active_note(past)
        self.assertEqual(note.aging_bucket, 'b365')

    def test_aging_current_when_active_in_date(self):
        # Theo công thức mới (Dư nợ gốc = amount − repaid):
        # KW active dù chưa giải ngân vẫn có outstanding > 0 (= amount
        # đã cam kết). Trong hạn → aging = 'current'.
        future = (date.today() + timedelta(days=100)).strftime('%Y-%m-%d')
        note = self._active_note(future, disb=False)
        self.assertEqual(note.aging_bucket, 'current')

    def test_aging_false_when_fully_paid(self):
        # Tất toán hoàn toàn → outstanding 0 → aging False
        future = (date.today() + timedelta(days=100)).strftime('%Y-%m-%d')
        note = self._active_note(future)  # disb=True (default)
        self.env['re.loan.note.repayment'].create({
            'note_id': note.id,
            'amount_principal': note.amount,
            'date': date.today().strftime('%Y-%m-%d')})
        note.invalidate_recordset(['principal_outstanding',
                                    'aging_bucket'])
        self.assertFalse(note.aging_bucket)

    # ----- Maturity reminder ---------------------------------------------
    def test_maturity_reminder_creates_activity(self):
        soon = (date.today() + timedelta(days=5)).strftime('%Y-%m-%d')
        note = self._active_note(soon)
        self.assertFalse(note.activity_ids)
        self.env['re.loan.note']._cron_maturity_reminder()
        acts = note.activity_ids.filtered(
            lambda a: a.summary == 'KW sắp đáo hạn')
        self.assertEqual(len(acts), 1)

    def test_maturity_reminder_no_duplicate(self):
        soon = (date.today() + timedelta(days=5)).strftime('%Y-%m-%d')
        note = self._active_note(soon)
        self.env['re.loan.note']._cron_maturity_reminder()
        self.env['re.loan.note']._cron_maturity_reminder()
        acts = note.activity_ids.filtered(
            lambda a: a.summary == 'KW sắp đáo hạn')
        self.assertEqual(len(acts), 1)

    def test_maturity_reminder_skips_far(self):
        far = (date.today() + timedelta(days=60)).strftime('%Y-%m-%d')
        note = self._active_note(far)
        self.env['re.loan.note']._cron_maturity_reminder()
        self.assertFalse(note.activity_ids.filtered(
            lambda a: a.summary == 'KW sắp đáo hạn'))
