# -*- coding: utf-8 -*-
"""Tests Phase P1 — BBN KLCV workflow + rolled-up progress."""
from datetime import date, timedelta

from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install', 'rp_progress')
class TestProgressAcceptance(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Project
        cls.project = cls.env['re.project'].create({
            'name': 'Test Dự án X',
            'code': 'DUAN-X',
            'development_type': 'high_rise',
        })
        # Subzone (required cho rp.structure)
        cls.subzone = cls.env['re.subzone'].create({
            'name': 'Phân khu test',
            'code': 'SUB-1',
            'project_id': cls.project.id,
        })
        # Structure
        cls.structure = cls.env['rp.structure'].create({
            'name': 'Móng cọc',
            'code': 'MONG',
            'project_id': cls.project.id,
            'subzone_id': cls.subzone.id,
            'structure_level': 'item',
        })
        # Nhà thầu — chuẩn Odoo dùng res.partner với is_contractor=True
        cls.contractor = cls.env['res.partner'].create({
            'name': 'NT Test', 'is_company': True,
            'is_contractor': True})
        # Cost category — pre-existing seeded by rp_cost_base
        cls.category = cls.env['rp.cost.category'].search(
            [], limit=1)
        if not cls.category:
            cls.category = cls.env['rp.cost.category'].create({
                'code': 'TEST', 'name': 'Test Category'})
        # UOM
        cls.uom_m3 = cls.env.ref('rp_progress.uom_m3')
        # Tender package (required cho rp.contract)
        cls.tender = cls.env['rp.tender.package'].create({
            'name': 'Gói thầu test',
            'code': 'TP-1',
            'project_id': cls.project.id,
        })
        # Contract
        cls.contract = cls.env['rp.contract'].create({
            'name': 'HĐ-Test-001',
            'project_id': cls.project.id,
            'tender_package_id': cls.tender.id,
            'contractor_id': cls.contractor.id,
            'contract_value_pretax': 1_000_000_000.0,
            'sla_response_days': 7,
        })

    def _create_acceptance(self, date_submitted=None, lines=None):
        vals = {
            'contract_id': self.contract.id,
            'date_submitted': date_submitted or date(2026, 1, 15),
        }
        acc = self.env['rp.progress.acceptance'].create(vals)
        for line in lines or []:
            self.env['rp.progress.acceptance.line'].create({
                'acceptance_id': acc.id,
                'cost_category_id': line.get('category', self.category).id,
                'structure_id': line.get('structure', self.structure).id,
                'uom_id': line.get('uom', self.uom_m3).id,
                'description': line.get('desc', 'Test work'),
                'unit_price': line.get('price', 1_000_000.0),
                'quantity_estimated': line.get('qty_est', 100.0),
                'quantity_this_period': line.get('qty', 50.0),
            })
        return acc

    # ----- Auto sequence ------------------------------------------------
    def test_auto_sequence(self):
        acc = self._create_acceptance()
        self.assertNotEqual(acc.name, '/')
        self.assertIn('BBN', acc.name)

    # ----- Workflow -----------------------------------------------------
    def test_propose_requires_lines(self):
        acc = self._create_acceptance()
        # Không có dòng → đề xuất bị chặn
        with self.assertRaises(UserError):
            acc.action_propose()

    def test_workflow_draft_to_approved(self):
        acc = self._create_acceptance(
            lines=[{'qty': 30.0, 'qty_est': 100.0,
                    'price': 1_000_000.0}])
        self.assertEqual(acc.state, 'draft')
        acc.action_propose()
        self.assertEqual(acc.state, 'proposed')
        acc.action_approve()
        self.assertEqual(acc.state, 'approved')
        self.assertTrue(acc.date_approved)

    def test_cannot_approve_draft(self):
        acc = self._create_acceptance(lines=[{}])
        with self.assertRaises(UserError):
            acc.action_approve()

    def test_cannot_unlink_approved(self):
        acc = self._create_acceptance(lines=[{}])
        acc.action_propose()
        acc.action_approve()
        with self.assertRaises(UserError):
            acc.unlink()

    # ----- SLA overdue --------------------------------------------------
    def test_sla_overdue_detected(self):
        old_date = date.today() - timedelta(days=30)
        acc = self._create_acceptance(
            date_submitted=old_date,
            lines=[{}])
        acc.action_propose()
        # SLA 7 ngày, 30 ngày sau → overdue
        acc._compute_overdue_response()
        self.assertTrue(acc.is_overdue_response)
        self.assertGreater(acc.days_overdue, 20)

    def test_sla_not_overdue_when_within(self):
        acc = self._create_acceptance(
            date_submitted=date.today() - timedelta(days=2),
            lines=[{}])
        acc.action_propose()
        acc._compute_overdue_response()
        self.assertFalse(acc.is_overdue_response)

    # ----- Compute amounts ---------------------------------------------
    def test_line_amount_compute(self):
        acc = self._create_acceptance(lines=[
            {'qty': 30.0, 'qty_est': 100.0, 'price': 1_000_000.0}])
        line = acc.line_ids
        self.assertEqual(line.amount_this_period, 30_000_000.0)
        self.assertEqual(line.amount_to_date, 30_000_000.0)
        self.assertAlmostEqual(line.progress_percent, 30.0)

    def test_acceptance_total_rollup(self):
        acc = self._create_acceptance(lines=[
            {'qty': 30.0, 'qty_est': 100.0, 'price': 1_000_000.0,
             'desc': 'Đào đất'},
            {'qty': 20.0, 'qty_est': 50.0, 'price': 2_000_000.0,
             'desc': 'Đổ bê tông'}])
        self.assertEqual(acc.line_count, 2)
        self.assertEqual(acc.total_value_period, 70_000_000.0)
        self.assertEqual(acc.total_value_to_date, 70_000_000.0)
        # Progress vs contract 1 tỷ → 7%
        self.assertAlmostEqual(acc.progress_percent, 7.0, places=2)

    # ----- Cumulative across BBN approved ------------------------------
    def test_cumulative_quantity_across_bbn(self):
        # BBN1: 30/100 m³
        acc1 = self._create_acceptance(
            date_submitted=date(2026, 1, 15),
            lines=[{'qty': 30.0, 'qty_est': 100.0,
                    'price': 1_000_000.0}])
        acc1.action_propose()
        acc1.action_approve()
        # BBN2: 40 m³ kỳ này → lũy kế phải = 70
        acc2 = self._create_acceptance(
            date_submitted=date(2026, 2, 15),
            lines=[{'qty': 40.0, 'qty_est': 100.0,
                    'price': 1_000_000.0}])
        line2 = acc2.line_ids
        line2._compute_qty_prev()
        line2._compute_qty_to_date()
        self.assertEqual(line2.quantity_to_date_prev, 30.0)
        self.assertEqual(line2.quantity_to_date, 70.0)
        self.assertEqual(line2.amount_to_date, 70_000_000.0)

    # ----- Validation: KL vượt dự toán ---------------------------------
    def test_quantity_cannot_exceed_estimated(self):
        with self.assertRaises(ValidationError):
            self._create_acceptance(lines=[
                {'qty': 150.0, 'qty_est': 100.0,
                 'price': 1_000_000.0}])

    # ----- Rolled-up: contract / structure / project -------------------
    def test_contract_progress_rollup(self):
        acc = self._create_acceptance(lines=[
            {'qty': 50.0, 'qty_est': 100.0, 'price': 1_000_000.0}])
        acc.action_propose()
        acc.action_approve()
        self.contract.invalidate_recordset(
            ['acceptance_value_to_date',
             'acceptance_progress_percent'])
        # Σ amount_to_date approved = 50 tr / contract 1 tỷ = 5%
        self.assertEqual(self.contract.acceptance_value_to_date,
                         50_000_000.0)
        self.assertAlmostEqual(
            self.contract.acceptance_progress_percent, 5.0, places=2)

    def test_structure_progress_rollup(self):
        acc = self._create_acceptance(lines=[
            {'qty': 50.0, 'qty_est': 100.0, 'price': 1_000_000.0}])
        acc.action_propose()
        acc.action_approve()
        self.structure.invalidate_recordset(
            ['progress_value', 'progress_percent', 'status'])
        self.assertEqual(self.structure.progress_value, 50_000_000.0)

    # ----- Date validation ---------------------------------------------
    def test_approval_date_must_not_be_before_submit(self):
        acc = self._create_acceptance(
            date_submitted=date(2026, 6, 15), lines=[{}])
        acc.action_propose()
        with self.assertRaises(ValidationError):
            acc.date_approved = date(2026, 5, 1)
