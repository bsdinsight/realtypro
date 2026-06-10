# -*- coding: utf-8 -*-
"""Khôi phục hạn mức cho facility revolving khi trả gốc KW.

Bug #15: Facility loại "Tuần hoàn (revolving)" phải tự động khôi phục
hạn mức khi KW trả gốc — vay 2 tỷ trên facility 10 tỷ, trả 1 tỷ thì
"còn lại" tăng từ 8 tỷ → 9 tỷ.
"""
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install', 're_loan')
class TestRevolvingRestoration(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bank = cls.env['res.partner'].create({
            'name': 'NH Revolve', 'is_company': True, 'is_bank': True})
        cls.contract = cls.env['re.loan.credit.contract'].create({
            'name': 'HĐTD-REV', 'partner_id': cls.bank.id,
            'amount_total': 10_000_000_000.0})
        cls.contract.action_activate()
        cls.facility = cls.env['re.loan.facility'].create({
            'name': 'Vốn lưu động',
            'credit_contract_id': cls.contract.id,
            'facility_type': 'revolving',
            'amount_limit': 10_000_000_000.0})

    def _new_note(self, name, amount):
        note = self.env['re.loan.note'].create({
            'name': name, 'facility_id': self.facility.id,
            'amount': amount, 'date_note': '2026-01-01',
            'tenor_months': 12, 'interest_rate': 9.0})
        note.action_activate()
        return note

    def test_revolving_restores_limit_after_principal_repayment(self):
        # Bước 1: hạn mức ban đầu — chưa rút gì
        self.assertEqual(self.facility.amount_used, 0.0)
        self.assertEqual(self.facility.amount_available,
                         10_000_000_000.0)

        # Bước 2: tạo KW vay 2 tỷ + giải ngân 2 tỷ
        note = self._new_note('KW-REV1', 2_000_000_000.0)
        self.env['re.loan.note.disbursement'].create({
            'note_id': note.id, 'amount': 2_000_000_000.0,
            'date': '2026-01-02'})
        self.facility.invalidate_recordset(
            ['amount_used', 'amount_available'])
        self.assertEqual(self.facility.amount_used, 2_000_000_000.0,
                         "Sau giải ngân 2 tỷ, đã sử dụng phải = 2 tỷ")
        self.assertEqual(self.facility.amount_available, 8_000_000_000.0,
                         "Sau giải ngân 2 tỷ, còn lại phải = 8 tỷ")

        # Bước 3: trả gốc 1 tỷ → hạn mức khôi phục
        self.env['re.loan.note.repayment'].create({
            'note_id': note.id,
            'amount_principal': 1_000_000_000.0,
            'date': '2026-02-01'})
        self.facility.invalidate_recordset(
            ['amount_used', 'amount_available'])
        self.assertEqual(self.facility.amount_used, 1_000_000_000.0,
                         "Sau trả gốc 1 tỷ, đã sử dụng phải = 1 tỷ "
                         "(revolving khôi phục)")
        self.assertEqual(self.facility.amount_available, 9_000_000_000.0,
                         "Sau trả gốc 1 tỷ, còn lại phải = 9 tỷ")

        # Bước 4: trả nốt 1 tỷ → khôi phục toàn bộ
        self.env['re.loan.note.repayment'].create({
            'note_id': note.id,
            'amount_principal': 1_000_000_000.0,
            'date': '2026-03-01'})
        self.facility.invalidate_recordset(
            ['amount_used', 'amount_available'])
        self.assertEqual(self.facility.amount_used, 0.0,
                         "Trả hết gốc, đã sử dụng phải = 0")
        self.assertEqual(self.facility.amount_available,
                         10_000_000_000.0,
                         "Trả hết gốc, hạn mức khôi phục đầy đủ")

    def test_term_facility_does_NOT_restore_limit(self):
        # Đối chứng: facility "Có kỳ hạn" KHÔNG khôi phục hạn mức.
        # Giảm revolving facility xuống 5 tỷ TRƯỚC (constraint Σ ≤ total
        # fire ngay lúc create), rồi tạo term 5 tỷ.
        self.facility.amount_limit = 5_000_000_000.0
        term = self.env['re.loan.facility'].create({
            'name': 'Vay đầu tư',
            'credit_contract_id': self.contract.id,
            'facility_type': 'term',
            'amount_limit': 5_000_000_000.0})

        note = self.env['re.loan.note'].create({
            'name': 'KW-TERM1', 'facility_id': term.id,
            'amount': 3_000_000_000.0, 'date_note': '2026-01-01',
            'tenor_months': 12, 'interest_rate': 9.0})
        note.action_activate()
        # Với term: amount_used = amount KW (3 tỷ), không phải outstanding
        term.invalidate_recordset(['amount_used', 'amount_available'])
        self.assertEqual(term.amount_used, 3_000_000_000.0)
        self.assertEqual(term.amount_available, 2_000_000_000.0)

        # Giải ngân + trả gốc 1 tỷ
        self.env['re.loan.note.disbursement'].create({
            'note_id': note.id, 'amount': 3_000_000_000.0,
            'date': '2026-01-02'})
        self.env['re.loan.note.repayment'].create({
            'note_id': note.id,
            'amount_principal': 1_000_000_000.0,
            'date': '2026-02-01'})
        term.invalidate_recordset(['amount_used', 'amount_available'])
        # Vẫn = 3 tỷ (amount KW), KHÔNG giảm xuống 2 tỷ
        self.assertEqual(term.amount_used, 3_000_000_000.0,
                         "Term KHÔNG khôi phục hạn mức khi trả gốc")
        self.assertEqual(term.amount_available, 2_000_000_000.0)
