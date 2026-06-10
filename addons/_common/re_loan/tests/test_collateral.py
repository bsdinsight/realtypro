# -*- coding: utf-8 -*-
"""
Tests L3 — tài sản thế chấp (collateral + valuation + pledge).
"""
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 're_loan')
class TestCollateral(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bank = cls.env['res.partner'].create({
            'name': 'NH Col', 'is_company': True, 'is_bank': True})
        cls.contract = cls.env['re.loan.credit.contract'].create({
            'name': 'HĐTD-COL', 'partner_id': cls.bank.id,
            'amount_total': 10_000_000_000.0})
        cls.contract.action_activate()
        cls.fac = cls.env['re.loan.facility'].create({
            'name': 'F-col', 'credit_contract_id': cls.contract.id,
            'facility_type': 'revolving', 'amount_limit': 10_000_000_000.0})
        cls.note = cls.env['re.loan.note'].create({
            'name': 'KW-COL', 'facility_id': cls.fac.id,
            'amount': 1_000_000_000.0, 'date_note': '2026-01-01',
            'tenor_months': 12, 'interest_rate': 10.0})
        cls.note.action_activate()
        cls.ctype = cls.env.ref('re_loan.collateral_type_real_estate')
        cls.col = cls.env['re.loan.collateral'].create({
            'name': 'Đất 123 Nguyễn Huệ', 'type_id': cls.ctype.id})
        # Định giá 10 tỷ để test state partial/fully_pledged
        cls.env['re.loan.collateral.valuation'].create({
            'collateral_id': cls.col.id, 'date': '2026-01-01',
            'amount': 10_000_000_000.0, 'method': 'appraisal'})

    # ----- Valuation ------------------------------------------------------
    def test_value_current_latest(self):
        self.env['re.loan.collateral.valuation'].create({
            'collateral_id': self.col.id, 'date': '2025-01-01',
            'amount': 5_000_000_000.0, 'method': 'appraisal'})
        self.env['re.loan.collateral.valuation'].create({
            'collateral_id': self.col.id, 'date': '2026-01-01',
            'amount': 6_000_000_000.0, 'method': 'market'})
        # giá trị hiện hành = lần định giá mới nhất
        self.assertEqual(self.col.value_current, 6_000_000_000.0)

    def test_valuation_negative_blocked(self):
        with self.assertRaises(ValidationError):
            self.env['re.loan.collateral.valuation'].create({
                'collateral_id': self.col.id, 'amount': -1.0})

    # ----- Pledge + state -------------------------------------------------
    def test_pledge_partial_state(self):
        # TS 10 tỷ, pledge 800M → partial_pledged (còn 9.2 tỷ)
        self.assertEqual(self.col.state, 'available')
        self.env['re.loan.collateral.pledge'].create({
            'collateral_id': self.col.id, 'note_id': self.note.id,
            'pledge_target': 'note',
            'secured_amount': 800_000_000.0})
        self.col.invalidate_recordset(
            ['state', 'total_secured', 'value_available'])
        self.assertEqual(self.col.state, 'partial_pledged')
        self.assertEqual(self.col.total_secured, 800_000_000.0)
        self.assertEqual(self.col.value_available, 9_200_000_000.0)

    def test_multi_pledge(self):
        note2 = self.env['re.loan.note'].create({
            'name': 'KW-COL2', 'facility_id': self.fac.id,
            'amount': 500_000_000.0, 'date_note': '2026-02-01',
            'tenor_months': 6, 'interest_rate': 10.0})
        note2.action_activate()
        self.env['re.loan.collateral.pledge'].create({
            'collateral_id': self.col.id, 'note_id': self.note.id,
            'pledge_target': 'note',
            'secured_amount': 600_000_000.0})
        self.env['re.loan.collateral.pledge'].create({
            'collateral_id': self.col.id, 'note_id': note2.id,
            'pledge_target': 'note',
            'secured_amount': 400_000_000.0})
        self.assertEqual(self.col.pledge_count, 2)
        self.assertEqual(self.col.total_secured, 1_000_000_000.0)

    def test_pledge_requires_contract(self):
        # Cấp 'contract' (default) cần credit_contract_id
        with self.assertRaises(ValidationError):
            self.env['re.loan.collateral.pledge'].create({
                'collateral_id': self.col.id,
                'pledge_target': 'contract',
                'secured_amount': 100_000_000.0})

    def test_pledge_facility_requires_facility(self):
        with self.assertRaises(ValidationError):
            self.env['re.loan.collateral.pledge'].create({
                'collateral_id': self.col.id,
                'pledge_target': 'facility',
                'secured_amount': 100_000_000.0})

    def test_pledge_note_requires_note(self):
        with self.assertRaises(ValidationError):
            self.env['re.loan.collateral.pledge'].create({
                'collateral_id': self.col.id,
                'pledge_target': 'note',
                'secured_amount': 100_000_000.0})

    def test_pledge_partner_from_note(self):
        pledge = self.env['re.loan.collateral.pledge'].create({
            'collateral_id': self.col.id, 'note_id': self.note.id,
            'pledge_target': 'note',
            'secured_amount': 100_000_000.0})
        self.assertEqual(pledge.partner_id, self.bank)

    # ----- Release --------------------------------------------------------
    def test_release_returns_to_available(self):
        pledge = self.env['re.loan.collateral.pledge'].create({
            'collateral_id': self.col.id, 'note_id': self.note.id,
            'pledge_target': 'note',
            'secured_amount': 800_000_000.0})
        self.col.invalidate_recordset(['state'])
        self.assertEqual(self.col.state, 'partial_pledged')
        pledge.action_release()
        self.assertEqual(pledge.state, 'released')
        self.assertTrue(pledge.release_date)
        self.col.invalidate_recordset(
            ['state', 'total_secured', 'value_available'])
        self.assertEqual(self.col.state, 'available')
        self.assertEqual(self.col.total_secured, 0.0)
        self.assertEqual(self.col.value_available, 10_000_000_000.0)

    def test_cannot_release_twice(self):
        pledge = self.env['re.loan.collateral.pledge'].create({
            'collateral_id': self.col.id, 'note_id': self.note.id,
            'pledge_target': 'note',
            'secured_amount': 800_000_000.0})
        pledge.action_release()
        with self.assertRaises(UserError):
            pledge.action_release()

    def test_pledge_at_contract_level(self):
        # Cấp HĐTD (default) — chuẩn nghiệp vụ VN
        pledge = self.env['re.loan.collateral.pledge'].create({
            'collateral_id': self.col.id,
            'pledge_target': 'contract',
            'credit_contract_id': self.contract.id,
            'secured_amount': 2_000_000_000.0})
        self.assertEqual(pledge.partner_id, self.bank)
        self.col.invalidate_recordset(['state'])
        # TS 10 tỷ, đem 2 tỷ → còn dư 8 tỷ → partial_pledged
        self.assertEqual(self.col.state, 'partial_pledged')

    def test_multi_bank_pledge_remaining_value(self):
        # TS 10 tỷ. Pledge HĐTD BIDV 4 tỷ, sau pledge HĐTD VCB 3 tỷ
        # → Σ 7 tỷ → còn lại 3 tỷ → vẫn partial_pledged
        vcb = self.env['res.partner'].create({
            'name': 'VCB Test', 'is_company': True, 'is_bank': True})
        contract2 = self.env['re.loan.credit.contract'].create({
            'name': 'HĐTD-VCB', 'partner_id': vcb.id,
            'amount_total': 5_000_000_000.0})
        contract2.action_activate()
        # BIDV pledge 4 tỷ
        self.env['re.loan.collateral.pledge'].create({
            'collateral_id': self.col.id,
            'pledge_target': 'contract',
            'credit_contract_id': self.contract.id,
            'secured_amount': 4_000_000_000.0})
        # VCB pledge 3 tỷ
        self.env['re.loan.collateral.pledge'].create({
            'collateral_id': self.col.id,
            'pledge_target': 'contract',
            'credit_contract_id': contract2.id,
            'secured_amount': 3_000_000_000.0})
        self.col.invalidate_recordset(
            ['state', 'total_secured', 'value_available',
             'active_pledge_count'])
        self.assertEqual(self.col.active_pledge_count, 2)
        self.assertEqual(self.col.total_secured, 7_000_000_000.0)
        self.assertEqual(self.col.value_available, 3_000_000_000.0)
        self.assertEqual(self.col.state, 'partial_pledged')

    def test_fully_pledged_state(self):
        # TS 10 tỷ, đem 10 tỷ → fully_pledged
        self.env['re.loan.collateral.pledge'].create({
            'collateral_id': self.col.id,
            'pledge_target': 'contract',
            'credit_contract_id': self.contract.id,
            'secured_amount': 10_000_000_000.0})
        self.col.invalidate_recordset(
            ['state', 'value_available'])
        self.assertEqual(self.col.state, 'fully_pledged')
        self.assertEqual(self.col.value_available, 0.0)

    def test_over_pledged_warning(self):
        # Single pledge với secured > value_current sẽ bị
        # _check_secured_within_value chặn. Test state over_pledged
        # phải mock qua 2 pledges (sum > value).
        # TS 10 tỷ. Pledge 1: 8 tỷ (active). Pledge 2: 3 tỷ → Σ 11 tỷ.
        contract2 = self.env['re.loan.credit.contract'].create({
            'name': 'HĐTD-2',
            'partner_id': self.bank.id,
            'amount_total': 5_000_000_000.0})
        contract2.action_activate()
        # Pledge 1: 8 tỷ (OK, còn 2 tỷ)
        self.env['re.loan.collateral.pledge'].create({
            'collateral_id': self.col.id,
            'pledge_target': 'contract',
            'credit_contract_id': self.contract.id,
            'secured_amount': 8_000_000_000.0})
        # Pledge 2: 3 tỷ — bị chặn (vượt 2 tỷ còn lại)
        with self.assertRaises(ValidationError):
            self.env['re.loan.collateral.pledge'].create({
                'collateral_id': self.col.id,
                'pledge_target': 'contract',
                'credit_contract_id': contract2.id,
                'secured_amount': 3_000_000_000.0})

    def test_secured_amount_capped_by_value_available(self):
        # TS 10 tỷ chưa có pledge → max = 10 tỷ. Pledge 11 tỷ → chặn.
        with self.assertRaises(ValidationError):
            self.env['re.loan.collateral.pledge'].create({
                'collateral_id': self.col.id,
                'pledge_target': 'contract',
                'credit_contract_id': self.contract.id,
                'secured_amount': 11_000_000_000.0})

    def test_secured_amount_allows_remaining(self):
        # Pledge 1: 6 tỷ → còn 4 tỷ. Pledge 2: 4 tỷ → OK (đúng max).
        contract2 = self.env['re.loan.credit.contract'].create({
            'name': 'HĐTD-2b', 'partner_id': self.bank.id,
            'amount_total': 5_000_000_000.0})
        contract2.action_activate()
        self.env['re.loan.collateral.pledge'].create({
            'collateral_id': self.col.id,
            'pledge_target': 'contract',
            'credit_contract_id': self.contract.id,
            'secured_amount': 6_000_000_000.0})
        # Đúng max → cho phép
        p2 = self.env['re.loan.collateral.pledge'].create({
            'collateral_id': self.col.id,
            'pledge_target': 'contract',
            'credit_contract_id': contract2.id,
            'secured_amount': 4_000_000_000.0})
        self.assertEqual(p2.state, 'active')

    def test_pledge_at_facility_level(self):
        # Cấp Facility — pledge cho 1 facility cụ thể
        pledge = self.env['re.loan.collateral.pledge'].create({
            'collateral_id': self.col.id,
            'pledge_target': 'facility',
            'facility_id': self.fac.id,
            'secured_amount': 1_500_000_000.0})
        # credit_contract_id auto-fill từ facility
        self.assertEqual(pledge.credit_contract_id, self.contract)

    def test_kw_inherits_pledge_from_contract(self):
        # Pledge cấp HĐTD → KW dưới HĐTD đó kế thừa qua all_pledge_ids
        pledge = self.env['re.loan.collateral.pledge'].create({
            'collateral_id': self.col.id,
            'pledge_target': 'contract',
            'credit_contract_id': self.contract.id,
            'secured_amount': 2_000_000_000.0})
        self.note.invalidate_recordset(['all_pledge_ids', 'pledge_count'])
        self.assertIn(pledge, self.note.all_pledge_ids)
        self.assertEqual(self.note.pledge_count, 1)

    def test_kw_inherits_pledge_from_facility(self):
        pledge = self.env['re.loan.collateral.pledge'].create({
            'collateral_id': self.col.id,
            'pledge_target': 'facility',
            'facility_id': self.fac.id,
            'secured_amount': 1_000_000_000.0})
        self.note.invalidate_recordset(['all_pledge_ids', 'pledge_count'])
        self.assertIn(pledge, self.note.all_pledge_ids)

    def test_kw_direct_pledge_in_direct_ids(self):
        # Pledge riêng KW (cấp 'note') xuất hiện ở direct_pledge_ids
        self.env['re.loan.collateral.pledge'].create({
            'collateral_id': self.col.id,
            'note_id': self.note.id,
            'pledge_target': 'note',
            'secured_amount': 500_000_000.0})
        self.assertEqual(len(self.note.direct_pledge_ids), 1)
