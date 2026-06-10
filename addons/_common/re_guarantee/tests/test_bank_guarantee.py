# -*- coding: utf-8 -*-
"""Tests cho module re_guarantee — chứng thư BL."""
from datetime import date, timedelta

from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install', 're_guarantee')
class TestBankGuarantee(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bank = cls.env['res.partner'].create({
            'name': 'NH BL Test', 'is_company': True, 'is_bank': True})
        cls.applicant = cls.env['res.partner'].create({
            'name': 'CC1 Applicant', 'is_company': True})
        cls.beneficiary = cls.env['res.partner'].create({
            'name': 'CĐT Beneficiary', 'is_company': True})
        cls.contract = cls.env['re.loan.credit.contract'].create({
            'name': 'HĐTD-BL', 'partner_id': cls.bank.id,
            'amount_total': 30_000_000_000.0})
        cls.contract.action_activate()
        cls.facility = cls.env['re.loan.facility'].create({
            'name': 'F-BL', 'credit_contract_id': cls.contract.id,
            'facility_type': 'guarantee_line',
            'purpose': 'bank_guarantee',
            'amount_limit': 30_000_000_000.0})

    def _bl(self, amount=10_000_000_000.0, type_='performance',
            issue=None, expiry=None):
        return self.env['re.bank.guarantee'].create({
            'guarantee_type': type_,
            'issuing_bank_partner_id': self.bank.id,
            'applicant_partner_id': self.applicant.id,
            'beneficiary_partner_id': self.beneficiary.id,
            'date_issue': issue or '2026-01-01',
            'date_expiry': expiry or '2026-12-31',
            'amount': amount,
            'guarantee_fee_rate': 1.5,
            'deposit_rate': 5.0,
            'facility_id': self.facility.id,
        })

    # ----- Sequence + dates -----
    def test_auto_sequence(self):
        bl = self._bl()
        self.assertNotEqual(bl.name, '/')
        self.assertIn('BL', bl.name)

    def test_expiry_must_be_after_issue(self):
        with self.assertRaises(ValidationError):
            self._bl(issue='2026-06-01', expiry='2026-01-01')

    def test_amount_must_be_positive(self):
        with self.assertRaises(ValidationError):
            self._bl(amount=0.0)

    # ----- Auto compute fees -----
    def test_fee_amount_compute(self):
        # 10 tỷ × 1.5%/năm × 365/365 = 150tr
        bl = self._bl(issue='2026-01-01', expiry='2026-12-31')
        # delta = 364 ngày → 10t × 1.5% × 364/365 ≈ 149.589.041
        self.assertAlmostEqual(
            bl.guarantee_fee_amount,
            10_000_000_000.0 * 0.015 * 364 / 365.0,
            delta=1)

    def test_deposit_amount_compute(self):
        bl = self._bl()
        self.assertEqual(bl.deposit_amount, 500_000_000.0)  # 10t × 5%

    # ----- Workflow -----
    def test_workflow_draft_to_released(self):
        bl = self._bl()
        self.assertEqual(bl.state, 'draft')
        bl.action_issue()
        self.assertEqual(bl.state, 'issued')
        bl.action_release()
        self.assertEqual(bl.state, 'released')
        self.assertTrue(bl.date_released)

    def test_cannot_release_draft(self):
        bl = self._bl()
        with self.assertRaises(UserError):
            bl.action_release()

    def test_forfeit_workflow(self):
        bl = self._bl()
        bl.action_issue()
        bl.forfeit_amount = 8_000_000_000.0
        bl.forfeit_reason = 'CC1 vi phạm tiến độ'
        bl.action_forfeit()
        self.assertEqual(bl.state, 'forfeited')
        self.assertTrue(bl.date_forfeited)

    # ----- Facility integration -----
    def test_facility_outstanding_includes_issued(self):
        bl1 = self._bl(amount=10_000_000_000.0)
        bl1.action_issue()
        bl2 = self._bl(amount=5_000_000_000.0)
        bl2.action_issue()
        self.facility.invalidate_recordset(
            ['guarantee_total_outstanding', 'guarantee_count'])
        self.assertEqual(self.facility.guarantee_count, 2)
        self.assertEqual(self.facility.guarantee_total_outstanding,
                         15_000_000_000.0)

    def test_facility_outstanding_excludes_released(self):
        bl1 = self._bl(amount=10_000_000_000.0)
        bl1.action_issue()
        bl1.action_release()
        self.facility.invalidate_recordset(['guarantee_total_outstanding'])
        self.assertEqual(self.facility.guarantee_total_outstanding, 0.0)

    # ----- Amendment: gia hạn -----
    def test_amendment_extension(self):
        bl = self._bl(expiry='2026-12-31')
        bl.action_issue()
        am = self.env['re.bank.guarantee.amendment'].create({
            'name': 'PL-EXT-01', 'guarantee_id': bl.id,
            'amendment_type': 'extension',
            'date_effective': '2026-12-01',
            'new_date_expiry': '2027-06-30'})
        am.action_apply()
        self.assertEqual(am.state, 'applied')
        self.assertEqual(str(bl.date_expiry), '2027-06-30')
        self.assertEqual(bl.state, 'extended')

    def test_amendment_amount_change(self):
        bl = self._bl(amount=10_000_000_000.0)
        bl.action_issue()
        am = self.env['re.bank.guarantee.amendment'].create({
            'name': 'PL-AMT-01', 'guarantee_id': bl.id,
            'amendment_type': 'amount',
            'date_effective': '2026-06-01',
            'new_amount': 15_000_000_000.0})
        am.action_apply()
        self.assertEqual(bl.amount, 15_000_000_000.0)

    # ----- Cron expiry -----
    def test_cron_auto_expire(self):
        # BL hết hạn 10 ngày trước hôm nay, vẫn issued
        bl = self._bl(
            issue=(date.today() - timedelta(days=370)).strftime('%Y-%m-%d'),
            expiry=(date.today() - timedelta(days=10)).strftime('%Y-%m-%d'),
        )
        bl.action_issue()
        self.env['re.bank.guarantee']._cron_check_expiry()
        self.assertEqual(bl.state, 'expired',
                         "BL quá hạn 10 ngày → auto expired")

    def test_cron_expiring_soon_creates_activity(self):
        # BL còn 15 ngày → tạo activity nhắc
        bl = self._bl(
            issue=(date.today() - timedelta(days=350)).strftime('%Y-%m-%d'),
            expiry=(date.today() + timedelta(days=15)).strftime('%Y-%m-%d'),
        )
        bl.action_issue()
        before = len(bl.activity_ids)
        self.env['re.bank.guarantee']._cron_check_expiry()
        bl.invalidate_recordset(['activity_ids'])
        after = len(bl.activity_ids)
        self.assertGreater(after, before,
                           "Cron phải tạo activity nhắc BL sắp hết hạn")
