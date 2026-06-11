# -*- coding: utf-8 -*-
"""
Tests L1b — re.loan.note + disbursement + repayment + facility limit wiring.
"""
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 're_loan')
class TestLoanNote(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bank = cls.env['res.partner'].create({
            'name': 'NH Test', 'is_company': True, 'is_bank': True})
        cls.contract = cls.env['re.loan.credit.contract'].create({
            'name': 'HĐTD-TEST', 'partner_id': cls.bank.id,
            'amount_total': 1_000_000_000.0})
        cls.contract.action_activate()
        cls.fac_rev = cls.env['re.loan.facility'].create({
            'name': 'Revolving', 'credit_contract_id': cls.contract.id,
            'facility_type': 'revolving', 'amount_limit': 600_000_000.0,
            'interest_rate_default': 9.0})
        cls.fac_term = cls.env['re.loan.facility'].create({
            'name': 'Term', 'credit_contract_id': cls.contract.id,
            'facility_type': 'term', 'amount_limit': 400_000_000.0,
            'interest_rate_default': 11.0})

    def _make_note(self, facility, amount, tenor=12):
        return self.env['re.loan.note'].create({
            'name': 'KW-%s-%s' % (facility.facility_type, amount),
            'facility_id': facility.id,
            'amount': amount,
            'date_note': '2026-01-01',
            'tenor_months': tenor,
        })

    # ----- KW basics ------------------------------------------------------
    def test_maturity_computed(self):
        note = self._make_note(self.fac_rev, 100_000_000.0, tenor=6)
        self.assertEqual(str(note.date_maturity), '2026-07-01')

    def test_amount_must_be_positive(self):
        """Draft cho phép amount=0 (user mới tạo, chưa có giải ngân).
        Nhưng khi gửi NH phải > 0.
        """
        # Draft + amount=0 → save OK
        note = self._make_note(self.fac_rev, 0.0)
        self.assertEqual(note.state, 'draft')
        # Gửi NH chặn amount=0
        with self.assertRaises(UserError):
            note.action_send_to_bank()
        # Amount âm — mọi state đều bị chặn (kể cả draft)
        with self.assertRaises(ValidationError):
            note.amount = -1.0

    def test_activate_requires_maturity(self):
        note = self.env['re.loan.note'].create({
            'name': 'KW-no-mat', 'facility_id': self.fac_rev.id,
            'amount': 100_000_000.0, 'date_note': '2026-01-01'})
        with self.assertRaises(UserError):
            note.action_activate()

    def test_activate_within_limit(self):
        note = self._make_note(self.fac_rev, 500_000_000.0)
        note.action_activate()
        self.assertEqual(note.state, 'active')

    def test_create_exceeds_limit_blocked(self):
        # Bug #17: constraint _check_amount_within_facility chặn NGAY
        # lúc tạo KW (trước đó chỉ chặn ở action_activate).
        with self.assertRaises(ValidationError):
            self._make_note(self.fac_rev, 700_000_000.0)  # > 600 limit

    # ----- Disbursement + outstanding ------------------------------------
    def test_disbursement_and_outstanding(self):
        # Dư nợ gốc = Số tiền KW − Đã trả gốc (KHÔNG phụ thuộc giải ngân).
        # KW 500M signed → nhận nợ toàn bộ 500M ngay từ ký, dù chỉ giải
        # ngân 300M (300M còn lại sẽ giải ngân sau theo tiến độ).
        note = self._make_note(self.fac_rev, 500_000_000.0)
        note.action_activate()
        self.env['re.loan.note.disbursement'].create({
            'note_id': note.id, 'date': '2026-01-05',
            'amount': 300_000_000.0})
        self.assertEqual(note.amount_disbursed, 300_000_000.0)
        # Dư nợ gốc = 500M − 0 = 500M (cam kết toàn bộ)
        self.assertEqual(note.principal_outstanding, 500_000_000.0)

    def test_disbursement_cannot_exceed_note(self):
        note = self._make_note(self.fac_rev, 500_000_000.0)
        note.action_activate()
        with self.assertRaises(ValidationError):
            self.env['re.loan.note.disbursement'].create({
                'note_id': note.id, 'amount': 600_000_000.0})

    # ----- Repayment lifecycle -------------------------------------------
    def test_partial_then_full_repayment(self):
        note = self._make_note(self.fac_rev, 500_000_000.0)
        note.action_activate()
        self.env['re.loan.note.disbursement'].create({
            'note_id': note.id, 'amount': 500_000_000.0})
        # partial
        self.env['re.loan.note.repayment'].create({
            'note_id': note.id, 'amount_principal': 200_000_000.0,
            'amount_interest': 10_000_000.0})
        self.assertEqual(note.state, 'partial_paid')
        self.assertEqual(note.principal_outstanding, 300_000_000.0)
        self.assertEqual(note.amount_repaid_interest, 10_000_000.0)
        # full
        self.env['re.loan.note.repayment'].create({
            'note_id': note.id, 'amount_principal': 300_000_000.0})
        self.assertEqual(note.state, 'fully_paid')
        self.assertEqual(note.principal_outstanding, 0.0)

    def test_repayment_cannot_exceed_disbursed(self):
        note = self._make_note(self.fac_rev, 500_000_000.0)
        note.action_activate()
        self.env['re.loan.note.disbursement'].create({
            'note_id': note.id, 'amount': 200_000_000.0})
        with self.assertRaises(ValidationError):
            self.env['re.loan.note.repayment'].create({
                'note_id': note.id, 'amount_principal': 300_000_000.0})

    # ----- Facility limit wiring -----------------------------------------
    def test_revolving_frees_limit_on_repay(self):
        note = self._make_note(self.fac_rev, 500_000_000.0)
        note.action_activate()
        self.env['re.loan.note.disbursement'].create({
            'note_id': note.id, 'amount': 500_000_000.0})
        self.assertEqual(self.fac_rev.amount_used, 500_000_000.0)
        self.assertEqual(self.fac_rev.amount_available, 100_000_000.0)
        # repay 200 → revolving frees it
        self.env['re.loan.note.repayment'].create({
            'note_id': note.id, 'amount_principal': 200_000_000.0})
        self.assertEqual(self.fac_rev.amount_used, 300_000_000.0)
        self.assertEqual(self.fac_rev.amount_available, 300_000_000.0)

    def test_term_does_not_free_on_repay(self):
        note = self._make_note(self.fac_term, 400_000_000.0)
        note.action_activate()
        self.env['re.loan.note.disbursement'].create({
            'note_id': note.id, 'amount': 400_000_000.0})
        # term: amount_used = committed amount (not outstanding)
        self.assertEqual(self.fac_term.amount_used, 400_000_000.0)
        self.env['re.loan.note.repayment'].create({
            'note_id': note.id, 'amount_principal': 100_000_000.0})
        # still committed (term không hoàn hạn mức)
        self.assertEqual(self.fac_term.amount_used, 400_000_000.0)

    def test_draft_note_does_not_consume_limit(self):
        self._make_note(self.fac_rev, 300_000_000.0)  # draft, not activated
        self.assertEqual(self.fac_rev.amount_used, 0.0)

    # ----- Overdue compute -----------------------------------------------
    def test_overdue_flag(self):
        note = self.env['re.loan.note'].create({
            'name': 'KW-overdue', 'facility_id': self.fac_rev.id,
            'amount': 100_000_000.0, 'date_note': '2020-01-01',
            'date_maturity': '2020-12-31'})
        note.action_activate()
        self.env['re.loan.note.disbursement'].create({
            'note_id': note.id, 'amount': 100_000_000.0})
        self.assertTrue(note.is_overdue)
        self.assertGreater(note.days_overdue, 0)

    # ----- Guards ---------------------------------------------------------
    def test_cannot_delete_note_with_disbursement(self):
        note = self._make_note(self.fac_rev, 100_000_000.0)
        note.action_activate()
        self.env['re.loan.note.disbursement'].create({
            'note_id': note.id, 'amount': 100_000_000.0})
        with self.assertRaises(UserError):
            note.unlink()

    def test_cannot_cancel_after_principal_repaid(self):
        note = self._make_note(self.fac_rev, 100_000_000.0)
        note.action_activate()
        self.env['re.loan.note.disbursement'].create({
            'note_id': note.id, 'amount': 100_000_000.0})
        self.env['re.loan.note.repayment'].create({
            'note_id': note.id, 'amount_principal': 50_000_000.0})
        with self.assertRaises(UserError):
            note.action_cancel()


@tagged('post_install', '-at_install', 're_loan')
class TestGuaranteeRelease(TransactionCase):
    """Bảo lãnh hết hạn → giải tỏa → hạn mức khôi phục."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bank = cls.env['res.partner'].create({
            'name': 'NH BL', 'is_company': True, 'is_bank': True})
        cls.contract = cls.env['re.loan.credit.contract'].create({
            'name': 'HĐTD-BL', 'partner_id': cls.bank.id,
            'amount_total': 30_000_000_000.0})
        cls.contract.action_activate()
        cls.fac_bl = cls.env['re.loan.facility'].create({
            'name': 'Hạn mức BL',
            'credit_contract_id': cls.contract.id,
            'facility_type': 'guarantee_line',
            'purpose': 'bank_guarantee',
            'amount_limit': 30_000_000_000.0})

    def _bl_note(self, amount, name='KW-BL'):
        note = self.env['re.loan.note'].create({
            'name': name, 'facility_id': self.fac_bl.id,
            'amount': amount, 'date_note': '2026-01-01',
            'tenor_months': 12, 'interest_rate': 2.0})
        return note

    def test_bl_active_chiem_han_muc(self):
        n = self._bl_note(10_000_000_000.0)
        n.action_activate()
        self.fac_bl.invalidate_recordset(['amount_used'])
        # BL phát hành 10 tỷ → chiếm 10 tỷ hạn mức
        self.assertEqual(self.fac_bl.amount_used, 10_000_000_000.0)
        self.assertEqual(self.fac_bl.amount_available, 20_000_000_000.0)

    def test_bl_release_khoi_phuc_han_muc(self):
        n = self._bl_note(10_000_000_000.0)
        n.action_activate()
        # Giải tỏa BL → state = fully_paid → hạn mức khôi phục
        n.action_release_guarantee()
        self.assertEqual(n.state, 'fully_paid')
        self.fac_bl.invalidate_recordset(
            ['amount_used', 'amount_available'])
        self.assertEqual(self.fac_bl.amount_used, 0.0,
                         "BL giải tỏa: hạn mức khôi phục")
        self.assertEqual(self.fac_bl.amount_available,
                         30_000_000_000.0)

    def test_action_release_blocked_on_term_facility(self):
        # action_release_guarantee chỉ áp dụng guarantee_line/lc_line.
        # Giảm fac_bl trước để có chỗ tạo fac_term (Σ ≤ HĐTD 30 tỷ).
        self.fac_bl.amount_limit = 29_000_000_000.0
        fac_term = self.env['re.loan.facility'].create({
            'name': 'F-term-test',
            'credit_contract_id': self.contract.id,
            'facility_type': 'term',
            'amount_limit': 1_000_000_000.0})
        n = self.env['re.loan.note'].create({
            'name': 'KW-term-test', 'facility_id': fac_term.id,
            'amount': 500_000_000.0, 'date_note': '2026-01-01',
            'tenor_months': 12, 'interest_rate': 9.0})
        n.action_activate()
        with self.assertRaises(UserError):
            n.action_release_guarantee()

    def test_bl_extension_van_chiem_han_muc(self):
        # Gia hạn BL: phụ lục extension → KW vẫn active → vẫn chiếm hm
        n = self._bl_note(10_000_000_000.0)
        n.action_activate()
        am = self.env['re.loan.note.amendment'].create({
            'name': 'PL-Gia-han-BL',
            'note_id': n.id,
            'amendment_type': 'extension',
            'new_date_maturity': '2027-12-31',
            'date_effective': '2026-12-01'})
        am.action_apply()
        self.fac_bl.invalidate_recordset(['amount_used'])
        # Sau gia hạn, KW vẫn active → vẫn chiếm 10 tỷ
        self.assertEqual(self.fac_bl.amount_used, 10_000_000_000.0)
        self.assertEqual(str(n.date_maturity), '2027-12-31')
