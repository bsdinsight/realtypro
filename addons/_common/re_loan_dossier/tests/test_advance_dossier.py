# -*- coding: utf-8 -*-
"""Việc 1432 — hồ sơ giải ngân cho TẠM ỨNG (chưa có hoá đơn).

Trả trước cho nhà thầu thì không ai xuất hoá đơn, nên phép kiểm lúc
gửi ngân hàng không được đòi hoá đơn của loại hồ sơ này — nhưng vẫn
phải đòi bên nhận tiền, vì ngân hàng cần biết tiền đi đâu.
"""
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 're_loan_dossier')
class TestAdvanceDossier(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bank = cls.env['res.partner'].create({
            'name': 'NH Test 1432', 'is_company': True, 'is_bank': True})
        cls.contractor = cls.env['res.partner'].create({
            'name': 'Nhà thầu 1432', 'is_company': True})
        # Giải ngân đòi TK ngân hàng của bên nhận tiền (chuẩn NH VN
        # chuyển thẳng cho nhà thầu).
        cls.contractor_bank = cls.env['res.partner.bank'].create({
            'acc_number': '0123456789-1432',
            'partner_id': cls.contractor.id})
        cls.contract = cls.env['re.loan.credit.contract'].create({
            'name': 'HĐTD-1432', 'partner_id': cls.bank.id,
            'amount_total': 1_000_000_000.0})
        cls.contract.action_activate()
        cls.facility = cls.env['re.loan.facility'].create({
            'name': 'Vay đầu tư 1432',
            'credit_contract_id': cls.contract.id,
            'facility_type': 'term', 'amount_limit': 900_000_000.0,
            'interest_rate_default': 10.0})
        cls.note = cls.env['re.loan.note'].create({
            'name': 'KW-1432', 'facility_id': cls.facility.id,
            'amount': 500_000_000.0, 'date_note': '2026-01-01',
            'tenor_months': 12})

    def _disbursement(self, amount=100_000_000.0):
        return self.env['re.loan.note.disbursement'].create({
            'note_id': self.note.id,
            'date': '2026-02-01',
            'amount': amount,
            'beneficiary_partner_id': self.contractor.id,
            'beneficiary_bank_account_id': self.contractor_bank.id,
        })

    def test_advance_dossier_submits_without_invoice(self):
        disb = self._disbursement()
        self.env['rp.loan.disbursement.dossier'].create({
            'disbursement_id': disb.id,
            'dossier_kind': 'advance',
            'advance_partner_id': self.contractor.id,
            'advance_reference': 'ĐNTU-01',
            'amount': 100_000_000.0,
        })
        disb.action_submit()
        self.assertEqual(disb.state, 'submitted')

    def test_advance_dossier_needs_partner(self):
        disb = self._disbursement()
        self.env['rp.loan.disbursement.dossier'].create({
            'disbursement_id': disb.id,
            'dossier_kind': 'advance',
            'amount': 100_000_000.0,
        })
        with self.assertRaises(UserError):
            disb.action_submit()

    def test_invoice_dossier_still_needs_invoice(self):
        disb = self._disbursement()
        self.env['rp.loan.disbursement.dossier'].create({
            'disbursement_id': disb.id,
            'amount': 100_000_000.0,
        })
        with self.assertRaises(UserError):
            disb.action_submit()

    def test_contractor_from_advance_partner(self):
        disb = self._disbursement()
        dossier = self.env['rp.loan.disbursement.dossier'].create({
            'disbursement_id': disb.id,
            'dossier_kind': 'advance',
            'advance_partner_id': self.contractor.id,
            'amount': 100_000_000.0,
        })
        self.assertEqual(dossier.contractor_id, self.contractor)
