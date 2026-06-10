# -*- coding: utf-8 -*-
"""Bug #17: KW không được nhập amount > Còn lại của facility."""
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install', 're_loan')
class TestAmountWithinFacility(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bank = cls.env['res.partner'].create({
            'name': 'NH Cap', 'is_company': True, 'is_bank': True})
        cls.contract = cls.env['re.loan.credit.contract'].create({
            'name': 'HĐTD-CAP', 'partner_id': cls.bank.id,
            'amount_total': 10_000_000_000.0})
        cls.contract.action_activate()
        cls.facility = cls.env['re.loan.facility'].create({
            'name': 'F-cap', 'credit_contract_id': cls.contract.id,
            'facility_type': 'term',
            'amount_limit': 1_000_000_000.0})

    def _create_note(self, amount, name='KW-T'):
        return self.env['re.loan.note'].create({
            'name': name, 'facility_id': self.facility.id,
            'amount': amount, 'date_note': '2026-01-01',
            'tenor_months': 12, 'interest_rate': 9.0})

    def test_draft_amount_within_limit_ok(self):
        # facility 1 tỷ, KW 800tr → OK
        note = self._create_note(800_000_000.0)
        self.assertEqual(note.state, 'draft')

    def test_draft_amount_exceeds_limit_blocked(self):
        # facility 1 tỷ, KW 1.5 tỷ → block
        with self.assertRaises(ValidationError):
            self._create_note(1_500_000_000.0)

    def test_second_note_blocked_when_first_active(self):
        # KW1 600tr active → còn lại 400tr; KW2 500tr → block
        n1 = self._create_note(600_000_000.0, 'KW-1')
        n1.action_activate()
        with self.assertRaises(ValidationError):
            self._create_note(500_000_000.0, 'KW-2')

    def test_second_note_within_remaining_ok(self):
        # KW1 600tr active → còn lại 400tr; KW2 400tr → OK
        n1 = self._create_note(600_000_000.0, 'KW-1')
        n1.action_activate()
        n2 = self._create_note(400_000_000.0, 'KW-2')
        self.assertEqual(n2.state, 'draft')

    def test_edit_active_note_amount_self_not_rejected(self):
        # KW active 500tr. User edit cùng giá trị 500tr — không bị
        # constraint tự reject vì KW chiếm 500tr đang được "trừ ra".
        n = self._create_note(500_000_000.0)
        n.action_activate()
        n.amount = 500_000_000.0  # No-op write, không raise
        self.assertEqual(n.amount, 500_000_000.0)

    def test_edit_active_note_amount_up_within_remaining_ok(self):
        # facility 1 tỷ. KW1 500tr active. Còn 500tr. Edit KW1 lên
        # 800tr (delta +300, vẫn ≤ 500 còn lại) → OK.
        n = self._create_note(500_000_000.0)
        n.action_activate()
        n.amount = 800_000_000.0
        self.assertEqual(n.amount, 800_000_000.0)

    def test_edit_active_note_amount_up_exceeds_remaining_blocked(self):
        # facility 1 tỷ. KW1 500tr active + KW2 300tr active.
        # Còn 200tr. Edit KW1 lên 800tr (delta +300, > 200) → block.
        n1 = self._create_note(500_000_000.0, 'KW-1')
        n1.action_activate()
        n2 = self._create_note(300_000_000.0, 'KW-2')
        n2.action_activate()
        with self.assertRaises(ValidationError):
            n1.amount = 800_000_000.0

    def test_revolving_commitment_blocks_new_kw(self):
        # Revolving facility 1 tỷ. KW1 amount=800tr active → outstanding
        # = amount (cam kết toàn bộ) = 800tr → facility.used = 800tr,
        # available = 200tr. KW2 amount=300tr → bị chặn (vượt 200tr
        # còn lại). Đúng nghiệp vụ: cam kết KW đã chiếm hạn mức ngay.
        self.facility.amount_limit = 100_000_000.0
        rev = self.env['re.loan.facility'].create({
            'name': 'F-rev', 'credit_contract_id': self.contract.id,
            'facility_type': 'revolving',
            'amount_limit': 1_000_000_000.0})
        n1 = self.env['re.loan.note'].create({
            'name': 'KW-REV-1', 'facility_id': rev.id,
            'amount': 800_000_000.0, 'date_note': '2026-01-01',
            'tenor_months': 12, 'interest_rate': 9.0})
        n1.action_activate()
        # KW1 active → outstanding 800tr (= amount), used 800tr, avail 200tr
        # KW2 300tr > 200tr → bị chặn
        with self.assertRaises(ValidationError):
            self.env['re.loan.note'].create({
                'name': 'KW-REV-2', 'facility_id': rev.id,
                'amount': 300_000_000.0, 'date_note': '2026-01-01',
                'tenor_months': 12, 'interest_rate': 9.0})
