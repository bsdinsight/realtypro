# -*- coding: utf-8 -*-
"""Tests for rp.contractor model and specialty seed."""

from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import UserError, ValidationError


@tagged('post_install', '-at_install', 'realty_contractor')
class TestRpContractor(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Contractor = cls.env['rp.contractor']
        cls.Specialty = cls.env['rp.contractor.specialty']

    # ----- Specialty seed tests

    def test_default_specialties_seeded(self):
        """Module install seeds 20 default Vietnamese specialties."""
        # Search by code prefix
        specs = self.Specialty.search([])
        # At least 20 — there may be user additions
        self.assertGreaterEqual(len(specs), 20,
            f'Expected at least 20 seeded specialties, got {len(specs)}')

    def test_seeded_specialty_codes_present(self):
        """Critical seeded codes exist."""
        for code in ['MONG', 'KCT', 'MEP', 'FACADE', 'PCCC', 'CANH_QUAN']:
            spec = self.Specialty.search([('code', '=', code)], limit=1)
            self.assertTrue(spec, f'Seeded specialty with code "{code}" missing')

    def test_specialty_code_unique(self):
        """Code must be unique."""
        with self.assertRaises(Exception):
            # SQL UNIQUE constraint
            self.Specialty.create({'name': 'Duplicate MONG', 'code': 'MONG'})

    # ----- Contractor basic CRUD

    def test_create_minimal_contractor(self):
        c = self.Contractor.create({
            'name': 'Công ty TNHH Test Contractor',
            'contractor_type': 'general',
        })
        self.assertEqual(c.state, 'prospect', 'Default state should be prospect')
        self.assertTrue(c.active)

    def test_contractor_with_specialties(self):
        mep = self.Specialty.search([('code', '=', 'MEP')], limit=1)
        kct = self.Specialty.search([('code', '=', 'KCT')], limit=1)
        c = self.Contractor.create({
            'name': 'Multi-skill Contractor',
            'contractor_type': 'general',
            'specialty_ids': [(4, mep.id), (4, kct.id)],
        })
        self.assertEqual(len(c.specialty_ids), 2)
        self.assertIn(mep, c.specialty_ids)

    # ----- Tax code validation

    def test_tax_code_10_digits_ok(self):
        c = self.Contractor.create({
            'name': 'Tax Test 10',
            'contractor_type': 'subcontractor',
            'tax_code': '0123456789',
        })
        self.assertEqual(c.tax_code, '0123456789')

    def test_tax_code_13_digits_ok(self):
        c = self.Contractor.create({
            'name': 'Tax Test 13',
            'contractor_type': 'subcontractor',
            'tax_code': '0123456789012',
        })
        self.assertTrue(c)

    def test_tax_code_with_hyphen_ok(self):
        """Mã số thuế kèm dấu - cũng hợp lệ."""
        c = self.Contractor.create({
            'name': 'Tax Test Hyphen',
            'contractor_type': 'subcontractor',
            'tax_code': '0123456789-001',
        })
        self.assertTrue(c)

    def test_tax_code_wrong_length_fails(self):
        with self.assertRaises(ValidationError):
            self.Contractor.create({
                'name': 'Bad Tax',
                'contractor_type': 'subcontractor',
                'tax_code': '12345',  # too short
            })

    def test_tax_code_non_numeric_fails(self):
        with self.assertRaises(ValidationError):
            self.Contractor.create({
                'name': 'Bad Tax 2',
                'contractor_type': 'subcontractor',
                'tax_code': 'ABCDEFGHIJ',  # letters
            })

    # ----- License expiry compute

    def test_license_expired_true(self):
        from datetime import date, timedelta
        c = self.Contractor.create({
            'name': 'Expired License',
            'contractor_type': 'general',
            'construction_license_expiry': date.today() - timedelta(days=1),
        })
        self.assertTrue(c.construction_license_expired)

    def test_license_expired_false_when_future(self):
        from datetime import date, timedelta
        c = self.Contractor.create({
            'name': 'Future License',
            'contractor_type': 'general',
            'construction_license_expiry': date.today() + timedelta(days=365),
        })
        self.assertFalse(c.construction_license_expired)

    def test_license_expired_false_when_empty(self):
        c = self.Contractor.create({
            'name': 'No License',
            'contractor_type': 'supplier',
        })
        self.assertFalse(c.construction_license_expired)

    # ----- State machine

    def test_approve_from_prospect(self):
        c = self.Contractor.create({
            'name': 'Approve Test',
            'contractor_type': 'general',
        })
        c.action_approve()
        self.assertEqual(c.state, 'approved')

    def test_suspend_from_approved(self):
        c = self.Contractor.create({
            'name': 'Suspend Test',
            'contractor_type': 'general',
        })
        c.action_approve()
        c.action_suspend()
        self.assertEqual(c.state, 'suspended')

    def test_reactivate_from_suspended(self):
        c = self.Contractor.create({
            'name': 'Reactivate Test',
            'contractor_type': 'general',
        })
        c.action_approve()
        c.action_suspend()
        c.action_approve()  # re-approve
        self.assertEqual(c.state, 'approved')

    def test_cannot_suspend_prospect(self):
        c = self.Contractor.create({
            'name': 'Bad Suspend',
            'contractor_type': 'general',
        })
        with self.assertRaises(UserError):
            c.action_suspend()

    def test_display_name_with_code(self):
        c = self.Contractor.create({
            'name': 'Display Test',
            'code': 'NT-DISP',
            'contractor_type': 'general',
        })
        self.assertEqual(c.display_name, '[NT-DISP] Display Test')

    def test_display_name_without_code(self):
        c = self.Contractor.create({
            'name': 'No Code Contractor',
            'contractor_type': 'supplier',
        })
        self.assertEqual(c.display_name, 'No Code Contractor')
