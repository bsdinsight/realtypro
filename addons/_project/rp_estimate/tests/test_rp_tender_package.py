# -*- coding: utf-8 -*-
"""Tests for rp.tender.package and line lifecycle + constraints."""

from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import ValidationError, UserError


@tagged('post_install', '-at_install', 'realty_estimate')
class TestRpTenderPackage(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Package = cls.env['rp.tender.package']
        cls.Line = cls.env['rp.tender.package.line']
        cls.Structure = cls.env['rp.structure']
        cls.Contractor = cls.env['res.partner']  # chuẩn Odoo dùng res.partner

        cls.project = cls.env['re.project'].create({
            'name': 'Tender Test Project',
            'code': 'TTP',
            'development_type': 'mixed',
        })
        cls.subzone_a = cls.env['re.subzone'].create({
            'name': 'Subzone A',
            'code': 'SZA',
            'project_id': cls.project.id,
        })
        cls.subzone_b = cls.env['re.subzone'].create({
            'name': 'Subzone B',
            'code': 'SZB',
            'project_id': cls.project.id,
        })
        cls.struct_a1 = cls.Structure.create({
            'project_id': cls.project.id,
            'subzone_id': cls.subzone_a.id,
            'structure_level': 'item',
            'structure_type': 'tower',
            'name': 'Tower A1',
        })
        cls.struct_a2 = cls.Structure.create({
            'project_id': cls.project.id,
            'subzone_id': cls.subzone_a.id,
            'structure_level': 'item',
            'structure_type': 'tower',
            'name': 'Tower A2',
        })
        cls.struct_b1 = cls.Structure.create({
            'project_id': cls.project.id,
            'subzone_id': cls.subzone_b.id,
            'structure_level': 'item',
            'structure_type': 'tower',
            'name': 'Tower B1',
        })
        cls.contractor = cls.Contractor.create({
            'name': 'Test Contractor for Tender',
            'is_contractor': True, 'is_company': True,
        })

    def test_create_basic_package(self):
        pkg = self.Package.create({
            'name': 'Test Package MEP',
            'project_id': self.project.id,
        })
        self.assertEqual(pkg.state, 'draft')
        self.assertEqual(pkg.line_count, 0)

    def test_add_lines_from_multiple_subzones(self):
        """Package can span multiple subzones."""
        pkg = self.Package.create({
            'name': 'Multi-zone Package',
            'project_id': self.project.id,
            'line_ids': [
                (0, 0, {'structure_id': self.struct_a1.id, 'estimated_amount': 100}),
                (0, 0, {'structure_id': self.struct_b1.id, 'estimated_amount': 200}),
            ],
        })
        self.assertEqual(pkg.line_count, 2)
        # Lines auto-derive subzone
        self.assertEqual(pkg.line_ids[0].subzone_id, self.subzone_a)
        self.assertEqual(pkg.line_ids[1].subzone_id, self.subzone_b)

    def test_subzone_coverage_computed(self):
        pkg = self.Package.create({
            'name': 'Coverage Test',
            'project_id': self.project.id,
            'line_ids': [
                (0, 0, {'structure_id': self.struct_a1.id}),
                (0, 0, {'structure_id': self.struct_b1.id}),
            ],
        })
        self.assertIn('Subzone A', pkg.subzone_coverage)
        self.assertIn('Subzone B', pkg.subzone_coverage)

    def test_unique_structure_per_package(self):
        """Cannot add same Hạng mục twice."""
        pkg = self.Package.create({
            'name': 'Unique Test',
            'project_id': self.project.id,
        })
        self.Line.create({
            'package_id': pkg.id,
            'structure_id': self.struct_a1.id,
        })
        with self.assertRaises(Exception):  # SQL unique constraint
            self.Line.create({
                'package_id': pkg.id,
                'structure_id': self.struct_a1.id,
            })

    def test_structure_must_match_project(self):
        """Line's structure must be in same project as package."""
        other_project = self.env['re.project'].create({
            'name': 'Other Project',
            'code': 'OP',
            'development_type': 'mixed',
        })
        other_subzone = self.env['re.subzone'].create({
            'name': 'Other Subzone',
            'code': 'OS',
            'project_id': other_project.id,
        })
        other_struct = self.Structure.create({
            'project_id': other_project.id,
            'subzone_id': other_subzone.id,
            'structure_level': 'item',
            'structure_type': 'tower',
            'name': 'Other Tower',
        })
        pkg = self.Package.create({
            'name': 'Mismatch Test',
            'project_id': self.project.id,
        })
        with self.assertRaises(ValidationError):
            self.Line.create({
                'package_id': pkg.id,
                'structure_id': other_struct.id,
            })

    def test_activate_requires_lines(self):
        pkg = self.Package.create({
            'name': 'Empty Activate',
            'project_id': self.project.id,
        })
        with self.assertRaises(UserError):
            pkg.action_activate()

    def test_activate_with_lines(self):
        pkg = self.Package.create({
            'name': 'Activate OK',
            'project_id': self.project.id,
            'line_ids': [(0, 0, {'structure_id': self.struct_a1.id})],
        })
        pkg.action_activate()
        self.assertEqual(pkg.state, 'active')

    def test_close_from_active(self):
        pkg = self.Package.create({
            'name': 'Close Test',
            'project_id': self.project.id,
            'line_ids': [(0, 0, {'structure_id': self.struct_a1.id})],
        })
        pkg.action_activate()
        pkg.action_close()
        self.assertEqual(pkg.state, 'closed')

    def test_contractor_link_optional(self):
        """Phase 2: contractor_id is optional."""
        pkg = self.Package.create({
            'name': 'No Contractor',
            'project_id': self.project.id,
        })
        self.assertFalse(pkg.contractor_id)
        # Can also set later
        pkg.contractor_id = self.contractor
        self.assertEqual(pkg.contractor_id, self.contractor)
