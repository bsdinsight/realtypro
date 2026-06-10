# -*- coding: utf-8 -*-
"""
Tests L4 — vay nội bộ (on-lending) trên re.loan.note (loan_type=onlending).
"""
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 're_loan')
class TestOnlending(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bank = cls.env['res.partner'].create({
            'name': 'NH OL', 'is_company': True, 'is_bank': True})
        cls.parent = cls.env['res.partner'].create({
            'name': 'CC1 Mẹ', 'is_company': True})
        cls.sub = cls.env['res.partner'].create({
            'name': 'CC1 Con A', 'is_company': True,
            'parent_company_id': cls.parent.id})
        cls.contract = cls.env['re.loan.credit.contract'].create({
            'name': 'HĐTD-OL', 'partner_id': cls.bank.id,
            'amount_total': 10_000_000_000.0})
        cls.contract.action_activate()
        cls.fac = cls.env['re.loan.facility'].create({
            'name': 'F-ol', 'credit_contract_id': cls.contract.id,
            'facility_type': 'revolving', 'amount_limit': 10_000_000_000.0})
        # KW nguồn (vay NH)
        cls.src = cls.env['re.loan.note'].create({
            'name': 'KW-SRC', 'facility_id': cls.fac.id,
            'amount': 5_000_000_000.0, 'date_note': '2026-01-01',
            'tenor_months': 12, 'interest_rate': 9.0})
        cls.src.action_activate()

    def _onlend(self, amount, rate=11.0):
        return self.env['re.loan.note'].create({
            'name': 'KW-OL-%s' % amount, 'loan_type': 'onlending',
            'source_note_id': self.src.id, 'counterparty_id': self.sub.id,
            'amount': amount, 'date_note': '2026-01-05',
            'tenor_months': 12, 'interest_rate': rate})

    # ----- Creation + links ----------------------------------------------
    def test_onlending_links(self):
        ol = self._onlend(2_000_000_000.0)
        # partner = công ty con; contract/currency từ KW nguồn
        self.assertEqual(ol.partner_id, self.sub)
        self.assertEqual(ol.credit_contract_id, self.contract)
        self.assertEqual(ol.currency_id, self.src.currency_id)

    def test_onlending_no_facility_needed(self):
        ol = self._onlend(1_000_000_000.0)
        self.assertFalse(ol.facility_id)
        ol.action_activate()
        self.assertEqual(ol.state, 'active')

    def test_source_amount_onlent_rollup(self):
        self._onlend(2_000_000_000.0)
        self._onlend(1_500_000_000.0)
        self.assertEqual(self.src.amount_onlent, 3_500_000_000.0)
        self.assertEqual(len(self.src.onlending_ids), 2)

    # ----- Constraints ----------------------------------------------------
    def test_onlending_requires_source(self):
        with self.assertRaises(ValidationError):
            self.env['re.loan.note'].create({
                'name': 'KW-bad', 'loan_type': 'onlending',
                'counterparty_id': self.sub.id, 'amount': 1_000_000_000.0,
                'date_note': '2026-01-05', 'tenor_months': 6,
                'interest_rate': 11.0})

    def test_onlending_requires_counterparty(self):
        with self.assertRaises(ValidationError):
            self.env['re.loan.note'].create({
                'name': 'KW-bad2', 'loan_type': 'onlending',
                'source_note_id': self.src.id, 'amount': 1_000_000_000.0,
                'date_note': '2026-01-05', 'tenor_months': 6,
                'interest_rate': 11.0})

    def test_external_requires_facility(self):
        with self.assertRaises(ValidationError):
            self.env['re.loan.note'].create({
                'name': 'KW-bad3', 'loan_type': 'external',
                'amount': 1_000_000_000.0, 'date_note': '2026-01-05',
                'tenor_months': 6, 'interest_rate': 9.0})

    def test_onlending_total_cannot_exceed_source(self):
        self._onlend(4_000_000_000.0)
        with self.assertRaises(ValidationError):
            self._onlend(2_000_000_000.0)  # 4 + 2 = 6 > 5 tỷ nguồn

    # ----- Rate warning ---------------------------------------------------
    def test_low_rate_warning_posted(self):
        # lãi cho vay lại (8%) < lãi nguồn (9%) → cảnh báo chatter, vẫn active
        ol = self._onlend(1_000_000_000.0, rate=8.0)
        ol.action_activate()
        self.assertEqual(ol.state, 'active')
        msgs = ol.message_ids.filtered(
            lambda m: m.body and 'Cảnh báo' in m.body)
        self.assertTrue(msgs)

    # ----- Full intercompany flow ----------------------------------------
    def test_onlending_disbursement_repayment(self):
        ol = self._onlend(2_000_000_000.0)
        ol.action_activate()
        self.env['re.loan.note.disbursement'].create({
            'note_id': ol.id, 'amount': 2_000_000_000.0,
            'date': '2026-01-06'})
        self.assertEqual(ol.principal_outstanding, 2_000_000_000.0)
        self.env['re.loan.note.repayment'].create({
            'note_id': ol.id, 'amount_principal': 2_000_000_000.0,
            'date': '2026-06-01'})
        self.assertEqual(ol.state, 'fully_paid')

    def test_onlending_has_interest_schedule(self):
        ol = self._onlend(1_200_000_000.0)
        ol.action_activate()
        self.assertEqual(len(ol.interest_line_ids), 12)
