# -*- coding: utf-8 -*-
"""Tests rp.contract core + state machine + computed amounts."""
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'rp_contract')
class TestRpContract(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.project = cls.env['re.project'].create({
            'name': 'TestProj Contract', 'code': 'TPC'})
        cls.subzone = cls.env['re.subzone'].create({
            'name': 'SZ1', 'project_id': cls.project.id, 'code': 'SZ'})
        cls.structure = cls.env['rp.structure'].create({
            'name': 'Tower S1', 'project_id': cls.project.id,
            'subzone_id': cls.subzone.id,
            'structure_level': 'item', 'structure_type': 'tower'})
        cls.contractor = cls.env['res.partner'].create({
            'is_contractor': True, 'is_company': True,
            'name': 'NT ABC', 'ref': 'NT-001'})
        cls.package = cls.env['rp.tender.package'].create({
            'name': 'Gói MEP', 'code': 'PK-001',
            'project_id': cls.project.id})
        cls.env['rp.tender.package.line'].create({
            'package_id': cls.package.id,
            'structure_id': cls.structure.id,
            'estimated_amount': 1_000_000_000.0})

    def _make_contract(self, value=1_000_000_000.0):
        return self.env['rp.contract'].create({
            'name': 'HD-2026/T01',
            'tender_package_id': self.package.id,
            'contractor_id': self.contractor.id,
            'contract_value_pretax': value,
            'vat_rate': 8.0,
            'advance_percent': 30.0,
            'retention_percent': 5.0})

    # ----- Computed amounts ----------------------------------------------
    def test_vat_and_total(self):
        c = self._make_contract()
        self.assertAlmostEqual(c.vat_amount, 80_000_000.0, delta=1)
        self.assertAlmostEqual(c.contract_value_total,
                               1_080_000_000.0, delta=1)

    def test_advance_retention(self):
        c = self._make_contract()
        # advance 30% sau thuế = 324tr
        self.assertAlmostEqual(c.amount_advance, 324_000_000.0, delta=1)
        # retention 5% = 54tr
        self.assertAlmostEqual(c.amount_retention, 54_000_000.0, delta=1)

    # ----- State machine -------------------------------------------------
    def test_sign_executing_complete(self):
        c = self._make_contract()
        self.assertEqual(c.state, 'draft')
        c.action_sign()
        self.assertEqual(c.state, 'signed')
        c.action_start_execution()
        self.assertEqual(c.state, 'executing')
        c.action_complete()
        self.assertEqual(c.state, 'completed')

    def test_sign_only_from_draft(self):
        c = self._make_contract()
        c.action_sign()
        with self.assertRaises(UserError):
            c.action_sign()

    def test_terminate_then_reset_draft(self):
        c = self._make_contract()
        c.action_sign()
        c.action_terminate()
        self.assertEqual(c.state, 'terminated')
        c.action_reset_draft()
        self.assertEqual(c.state, 'draft')

    # ----- Constraints ---------------------------------------------------
    def test_value_must_be_positive(self):
        with self.assertRaises(ValidationError):
            self._make_contract(value=0.0)

    def test_vat_rate_range(self):
        c = self._make_contract()
        with self.assertRaises(ValidationError):
            c.vat_rate = 150.0

    def test_unlink_only_draft(self):
        c = self._make_contract()
        c.action_sign()
        with self.assertRaises(UserError):
            c.unlink()

    # ----- BOQ lines -----------------------------------------------------
    def test_line_total_matches_contract_value(self):
        c = self._make_contract(value=1_000_000_000.0)
        # tổng line = 1 tỷ → OK
        self.env['rp.contract.line'].create({
            'contract_id': c.id, 'description': 'Phần A',
            'quantity': 100, 'unit_price': 6_000_000.0})
        self.env['rp.contract.line'].create({
            'contract_id': c.id, 'description': 'Phần B',
            'quantity': 200, 'unit_price': 2_000_000.0})
        self.assertEqual(c.line_total, 1_000_000_000.0)

    def test_line_total_must_match_contract_at_sign(self):
        c = self._make_contract(value=1_000_000_000.0)
        # tạo line lệch (500tr) — cho phép trong Nháp
        self.env['rp.contract.line'].create({
            'contract_id': c.id, 'description': 'Sai',
            'quantity': 100, 'unit_price': 5_000_000.0})
        # nhưng ký HĐ thì bị chặn
        with self.assertRaises(UserError):
            c.action_sign()

    # ----- Tender package smart button -----------------------------------
    def test_package_contract_count(self):
        self._make_contract()
        self._make_contract()
        self.assertEqual(self.package.contract_count, 2)

    def test_package_signed_value(self):
        c1 = self._make_contract()
        c1.action_sign()
        c2 = self._make_contract()  # vẫn draft → không tính
        self.assertAlmostEqual(self.package.contract_value_signed,
                               1_080_000_000.0, delta=1)
