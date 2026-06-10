# -*- coding: utf-8 -*-
"""
Tests L1a — re.loan.credit.contract + re.loan.facility.
"""
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 're_loan')
class TestCreditContract(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bank = cls.env['res.partner'].create({
            'name': 'Ngân hàng BIDV',
            'is_company': True,
            'is_bank': True,
        })
        cls.contract = cls.env['re.loan.credit.contract'].create({
            'name': 'HĐTD-01/2026',
            'partner_id': cls.bank.id,
            'amount_total': 500_000_000_000.0,  # 500 tỷ
        })

    # ----- Contract basics ------------------------------------------------
    def test_default_state_draft(self):
        self.assertEqual(self.contract.state, 'draft')

    def test_default_currency_company(self):
        self.assertEqual(self.contract.currency_id,
                         self.env.company.currency_id)

    # ----- State machine --------------------------------------------------
    def test_activate(self):
        self.contract.action_activate()
        self.assertEqual(self.contract.state, 'active')

    def test_activate_only_from_draft(self):
        self.contract.action_activate()
        with self.assertRaises(UserError):
            self.contract.action_activate()

    def test_close_flow(self):
        self.contract.action_activate()
        self.contract.action_close()
        self.assertEqual(self.contract.state, 'closed')

    def test_cannot_cancel_closed(self):
        self.contract.action_activate()
        self.contract.action_close()
        with self.assertRaises(UserError):
            self.contract.action_cancel()

    def test_cancel_then_reset(self):
        self.contract.action_cancel()
        self.assertEqual(self.contract.state, 'cancelled')
        self.contract.action_reset_draft()
        self.assertEqual(self.contract.state, 'draft')

    # ----- Facility + limit math -----------------------------------------
    def test_facility_total_and_available(self):
        self.env['re.loan.facility'].create({
            'name': 'Hạn mức revolving',
            'credit_contract_id': self.contract.id,
            'facility_type': 'revolving',
            'amount_limit': 300_000_000_000.0,
        })
        self.env['re.loan.facility'].create({
            'name': 'Hạn mức term',
            'credit_contract_id': self.contract.id,
            'facility_type': 'term',
            'amount_limit': 150_000_000_000.0,
        })
        self.assertEqual(self.contract.facility_count, 2)
        self.assertEqual(self.contract.amount_facility_total,
                         450_000_000_000.0)
        self.assertEqual(self.contract.amount_facility_available,
                         50_000_000_000.0)

    def test_facility_total_cannot_exceed_contract(self):
        with self.assertRaises(ValidationError):
            self.env['re.loan.facility'].create({
                'name': 'Hạn mức vượt',
                'credit_contract_id': self.contract.id,
                'facility_type': 'revolving',
                'amount_limit': 600_000_000_000.0,  # > 500 tỷ
            })

    def test_facility_defaults(self):
        fac = self.env['re.loan.facility'].create({
            'name': 'F1',
            'credit_contract_id': self.contract.id,
            'facility_type': 'revolving',
            'amount_limit': 100_000_000_000.0,
        })
        # OQ-2 / TQ-4 defaults
        self.assertEqual(fac.interest_method, 'declining')
        self.assertEqual(fac.day_count, 'act_360')
        # L1a placeholder: chưa có note → used 0, available = limit
        self.assertEqual(fac.amount_used, 0.0)
        self.assertEqual(fac.amount_available, 100_000_000_000.0)
        # related fields
        self.assertEqual(fac.currency_id, self.contract.currency_id)
        self.assertEqual(fac.company_id, self.contract.company_id)

    # ----- Guards ---------------------------------------------------------
    def test_cannot_delete_contract_with_facility(self):
        self.env['re.loan.facility'].create({
            'name': 'F1',
            'credit_contract_id': self.contract.id,
            'facility_type': 'revolving',
            'amount_limit': 100_000_000_000.0,
        })
        with self.assertRaises(UserError):
            self.contract.unlink()

    def test_contract_date_validation(self):
        with self.assertRaises(ValidationError):
            self.contract.write({
                'date_start': '2026-12-31',
                'date_end': '2026-01-01',
            })


@tagged('post_install', '-at_install', 're_loan')
class TestFlexibleLimits(TransactionCase):
    """Test pool liên thông per-facility.

    Spec:
      - flexible_limits là cờ TRÊN TỪNG facility (không phải HĐTD)
      - Σ limit ≤ total HĐTD: hard rule, luôn áp dụng
      - Facility flex chia sẻ pool với các facility KHÁC cũng flex
      - Facility không flex giữ limit cứng

    Setup test:
      HĐTD 1000 tỷ
        ├── F_loan (flex, limit 600)   ┐ Pool flex = 900
        ├── F_bg   (flex, limit 300)   ┘
        └── F_lc   (no-flex, limit 100)   Limit cứng riêng
      Σ limit = 1000 = total ✓
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bank = cls.env['res.partner'].create({
            'name': 'NH Flex', 'is_company': True, 'is_bank': True})
        cls.contract = cls.env['re.loan.credit.contract'].create({
            'name': 'HĐTD-FLEX', 'partner_id': cls.bank.id,
            'amount_total': 1_000_000_000.0})
        cls.contract.action_activate()
        cls.fac_loan = cls.env['re.loan.facility'].create({
            'name': 'Vay đầu tư',
            'credit_contract_id': cls.contract.id,
            'facility_type': 'revolving',
            'amount_limit': 600_000_000.0,
            'flexible_limits': True})
        cls.fac_bg = cls.env['re.loan.facility'].create({
            'name': 'Bảo lãnh',
            'credit_contract_id': cls.contract.id,
            'facility_type': 'guarantee_line',
            'amount_limit': 300_000_000.0,
            'flexible_limits': True})
        cls.fac_lc = cls.env['re.loan.facility'].create({
            'name': 'L/C',
            'credit_contract_id': cls.contract.id,
            'facility_type': 'lc_line',
            'amount_limit': 100_000_000.0,
            'flexible_limits': False})

    def test_sum_limit_must_not_exceed_total(self):
        # Σ 600+300+100 = 1000 = total — OK
        self.assertEqual(self.contract.amount_facility_total,
                         1_000_000_000.0)
        # Thêm 1 facility 1 đồng → vượt total → bị chặn
        with self.assertRaises(ValidationError):
            self.env['re.loan.facility'].create({
                'name': 'Z', 'credit_contract_id': self.contract.id,
                'facility_type': 'term',
                'amount_limit': 1.0})

    def test_initial_available_pool_for_flex_own_for_strict(self):
        # Facility flex thấy pool = 900 (600+300), chưa dùng
        self.assertEqual(self.fac_loan.amount_available, 900_000_000.0)
        self.assertEqual(self.fac_bg.amount_available, 900_000_000.0)
        # Facility không flex thấy đúng limit riêng = 100
        self.assertEqual(self.fac_lc.amount_available, 100_000_000.0)

    def test_flex_share_pool_when_one_uses(self):
        # F_loan rút 500 → pool_used 500, pool_remaining 400.
        # F_loan & F_bg cùng thấy "Còn lại" = 400. F_lc không đổi.
        note = self.env['re.loan.note'].create({
            'name': 'KW-LOAN1', 'facility_id': self.fac_loan.id,
            'amount': 500_000_000.0, 'date_note': '2026-01-01',
            'tenor_months': 12, 'interest_rate': 9.0})
        note.action_activate()
        self.env['re.loan.note.disbursement'].create({
            'note_id': note.id, 'amount': 500_000_000.0})
        self.fac_loan.invalidate_recordset(['amount_available'])
        self.fac_bg.invalidate_recordset(['amount_available'])
        self.assertEqual(self.fac_loan.amount_available, 400_000_000.0)
        self.assertEqual(self.fac_bg.amount_available, 400_000_000.0)
        # F_lc không tham gia pool, giữ nguyên
        self.assertEqual(self.fac_lc.amount_available, 100_000_000.0)

    def test_strict_facility_uses_own_limit_only(self):
        # F_lc (no-flex) rút đúng limit 100 — OK
        note_lc = self.env['re.loan.note'].create({
            'name': 'KW-LC1', 'facility_id': self.fac_lc.id,
            'amount': 100_000_000.0, 'date_note': '2026-01-01',
            'tenor_months': 6, 'interest_rate': 6.0})
        note_lc.action_activate()
        self.env['re.loan.note.disbursement'].create({
            'note_id': note_lc.id, 'amount': 100_000_000.0})
        self.fac_lc.invalidate_recordset(['amount_available'])
        self.assertEqual(self.fac_lc.amount_available, 0.0)
        # Pool flex KHÔNG bị giảm bởi F_lc
        self.fac_loan.invalidate_recordset(['amount_available'])
        self.assertEqual(self.fac_loan.amount_available, 900_000_000.0)

    def test_has_flexible_facility_indicator(self):
        self.assertTrue(self.contract.has_flexible_facility)
        # Bỏ flag trên 2 facility flex → contract không còn flex
        (self.fac_loan + self.fac_bg).write({'flexible_limits': False})
        self.contract.invalidate_recordset(['has_flexible_facility'])
        self.assertFalse(self.contract.has_flexible_facility)


@tagged('post_install', '-at_install', 're_loan')
class TestFacilityProjectAllocation(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bank = cls.env['res.partner'].create({
            'name': 'NH Alloc', 'is_company': True, 'is_bank': True})
        cls.contract = cls.env['re.loan.credit.contract'].create({
            'name': 'HĐTD-ALLOC', 'partner_id': cls.bank.id,
            'amount_total': 100_000_000_000.0})  # 100 tỷ
        cls.contract.action_activate()
        # Facility GPMB 40 tỷ
        cls.fac_gpmb = cls.env['re.loan.facility'].create({
            'name': 'GPMB', 'credit_contract_id': cls.contract.id,
            'facility_type': 'term', 'purpose': 'investment_long',
            'amount_limit': 40_000_000_000.0})
        # Project A, B
        cls.proj_a = cls.env['re.project'].create({
            'name': 'Dự án A', 'code': 'DA-A'})
        cls.proj_b = cls.env['re.project'].create({
            'name': 'Dự án B', 'code': 'DA-B'})

    def test_allocate_within_facility_limit(self):
        self.env['re.loan.facility.project.allocation'].create({
            'facility_id': self.fac_gpmb.id,
            'project_id': self.proj_a.id,
            'amount': 30_000_000_000.0})
        self.env['re.loan.facility.project.allocation'].create({
            'facility_id': self.fac_gpmb.id,
            'project_id': self.proj_b.id,
            'amount': 10_000_000_000.0})
        self.assertEqual(self.fac_gpmb.amount_allocated_to_projects,
                         40_000_000_000.0)
        self.assertEqual(self.fac_gpmb.amount_unallocated, 0.0)

    def test_allocate_exceed_facility_blocked(self):
        self.env['re.loan.facility.project.allocation'].create({
            'facility_id': self.fac_gpmb.id,
            'project_id': self.proj_a.id,
            'amount': 35_000_000_000.0})
        # B muốn 10 → tổng 45 > 40, bị chặn
        with self.assertRaises(ValidationError):
            self.env['re.loan.facility.project.allocation'].create({
                'facility_id': self.fac_gpmb.id,
                'project_id': self.proj_b.id,
                'amount': 10_000_000_000.0})

    def test_negative_amount_blocked(self):
        with self.assertRaises(ValidationError):
            self.env['re.loan.facility.project.allocation'].create({
                'facility_id': self.fac_gpmb.id,
                'project_id': self.proj_a.id,
                'amount': -1.0})

    def test_purpose_related_from_facility(self):
        a = self.env['re.loan.facility.project.allocation'].create({
            'facility_id': self.fac_gpmb.id,
            'project_id': self.proj_a.id,
            'amount': 5_000_000_000.0})
        self.assertEqual(a.purpose, 'investment_long')
        self.assertEqual(a.credit_contract_id, self.contract)
