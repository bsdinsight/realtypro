# -*- coding: utf-8 -*-
"""Tests rp.loan.allocation — phân bổ vay theo công trình."""
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'rp_loan_bridge')
class TestLoanAllocation(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # ---- Realty Project skeleton ----
        cls.project = cls.env['re.project'].create({
            'name': 'Proj-Alloc', 'code': 'AL'})
        cls.subzone = cls.env['re.subzone'].create({
            'name': 'SZ-Alloc', 'project_id': cls.project.id, 'code': 'SZ'})
        cls.structure = cls.env['rp.structure'].create({
            'name': 'Tower-Alloc', 'project_id': cls.project.id,
            'subzone_id': cls.subzone.id,
            'structure_level': 'item', 'structure_type': 'tower'})
        # Cost category đã được auto-seed (incl 9.1 Lãi vay) khi tạo project
        cls.cost_cat_interest = cls.env['rp.cost.category'].search([
            ('project_id', '=', cls.project.id),
            ('code', '=', '9.1')], limit=1)
        cls.contractor = cls.env['res.partner'].create({
            'is_contractor': True, 'is_company': True,
            'name': 'NT-Alloc', 'ref': 'NT-AL'})
        cls.package = cls.env['rp.tender.package'].create({
            'name': 'Pkg-Alloc', 'project_id': cls.project.id})
        cls.env['rp.tender.package.line'].create({
            'package_id': cls.package.id,
            'structure_id': cls.structure.id})
        cls.contract = cls.env['rp.contract'].create({
            'name': 'HD-Alloc', 'tender_package_id': cls.package.id,
            'contractor_id': cls.contractor.id,
            'contract_value_pretax': 10_000_000_000.0,
            'vat_rate': 8.0})
        # ---- Loan setup ----
        cls.bank = cls.env['res.partner'].create({
            'name': 'NH-Alloc', 'is_company': True, 'is_bank': True})
        cls.credit = cls.env['re.loan.credit.contract'].create({
            'name': 'HĐTD-AL', 'partner_id': cls.bank.id,
            'amount_total': 100_000_000_000.0})
        cls.credit.action_activate()
        cls.facility = cls.env['re.loan.facility'].create({
            'name': 'F-AL', 'credit_contract_id': cls.credit.id,
            'facility_type': 'revolving',
            'amount_limit': 100_000_000_000.0})
        cls.note = cls.env['re.loan.note'].create({
            'name': 'KW-AL', 'facility_id': cls.facility.id,
            'amount': 20_000_000_000.0, 'date_note': '2026-01-01',
            'tenor_months': 12, 'interest_rate': 10.0})
        cls.note.action_activate()

    # ----- Cost cat auto-seed -------------------------------------------
    def test_cost_category_91_seeded(self):
        self.assertTrue(self.cost_cat_interest)
        self.assertIn('Lãi vay', self.cost_cat_interest.name)

    # ----- Basic allocation ---------------------------------------------
    def test_allocate_interest_to_structure(self):
        a = self.env['rp.loan.allocation'].create({
            'note_id': self.note.id, 'project_id': self.project.id,
            'structure_id': self.structure.id,
            'cost_category_id': self.cost_cat_interest.id,
            'base': 'interest', 'method': 'percent', 'percent': 100.0})
        # base = interest_total_planned của KW (≈ 20e9 * 10% * ~1.014 = ~2.03e9 act_360)
        self.assertGreater(a.amount_allocated, 1_900_000_000.0)
        self.assertLess(a.amount_allocated, 2_100_000_000.0)

    def test_allocate_principal_percent(self):
        a = self.env['rp.loan.allocation'].create({
            'note_id': self.note.id, 'project_id': self.project.id,
            'structure_id': self.structure.id,
            'base': 'principal', 'method': 'percent', 'percent': 50.0})
        self.assertEqual(a.amount_allocated, 10_000_000_000.0)

    def test_allocate_amount_method(self):
        a = self.env['rp.loan.allocation'].create({
            'note_id': self.note.id, 'project_id': self.project.id,
            'structure_id': self.structure.id,
            'base': 'principal', 'method': 'amount',
            'amount': 3_000_000_000.0})
        self.assertEqual(a.amount_allocated, 3_000_000_000.0)

    def test_allocate_to_contract(self):
        a = self.env['rp.loan.allocation'].create({
            'note_id': self.note.id, 'project_id': self.project.id,
            'contract_id': self.contract.id,
            'base': 'principal', 'method': 'amount',
            'amount': 5_000_000_000.0})
        self.assertEqual(self.contract.loan_allocated_amount,
                         5_000_000_000.0)
        self.assertEqual(self.contract.loan_allocation_count, 1)

    # ----- Rollups -------------------------------------------------------
    def test_note_total_principal_interest(self):
        self.env['rp.loan.allocation'].create({
            'note_id': self.note.id, 'project_id': self.project.id,
            'structure_id': self.structure.id,
            'base': 'principal', 'method': 'amount',
            'amount': 5_000_000_000.0})
        self.env['rp.loan.allocation'].create({
            'note_id': self.note.id, 'project_id': self.project.id,
            'structure_id': self.structure.id,
            'base': 'interest', 'method': 'amount',
            'amount': 500_000_000.0})
        self.assertEqual(self.note.allocation_total_principal,
                         5_000_000_000.0)
        self.assertEqual(self.note.allocation_total_interest,
                         500_000_000.0)

    def test_structure_rollup(self):
        self.env['rp.loan.allocation'].create({
            'note_id': self.note.id, 'project_id': self.project.id,
            'structure_id': self.structure.id,
            'base': 'interest', 'method': 'amount',
            'amount': 800_000_000.0})
        self.assertEqual(self.structure.loan_allocated_amount,
                         800_000_000.0)

    # ----- Constraints ---------------------------------------------------
    def test_percent_range(self):
        with self.assertRaises(ValidationError):
            self.env['rp.loan.allocation'].create({
                'note_id': self.note.id, 'project_id': self.project.id,
                'base': 'principal', 'method': 'percent',
                'percent': 150.0})

    def test_negative_amount_blocked(self):
        with self.assertRaises(ValidationError):
            self.env['rp.loan.allocation'].create({
                'note_id': self.note.id, 'project_id': self.project.id,
                'base': 'principal', 'method': 'amount',
                'amount': -100.0})

    def test_structure_wrong_project(self):
        other = self.env['re.project'].create({
            'name': 'Other', 'code': 'OTH'})
        with self.assertRaises(ValidationError):
            self.env['rp.loan.allocation'].create({
                'note_id': self.note.id, 'project_id': other.id,
                'structure_id': self.structure.id,
                'base': 'principal', 'method': 'percent',
                'percent': 10.0})
