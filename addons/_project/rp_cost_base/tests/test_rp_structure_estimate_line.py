# -*- coding: utf-8 -*-
"""Tests for rp.structure.estimate.line (Khái toán inline)."""

from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import ValidationError


@tagged('post_install', '-at_install', 'realty_cost_base')
class TestRpStructureEstimateLine(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Structure = cls.env['rp.structure']
        cls.Line = cls.env['rp.structure.estimate.line']
        cls.Category = cls.env['rp.cost.category']

        cls.project = cls.env['re.project'].create({
            'name': 'Estimate Test Project',
            'code': 'ETP',
            'development_type': 'mixed',
        })
        cls.subzone = cls.env['re.subzone'].create({
            'name': 'Subzone E1',
            'code': 'E1',
            'project_id': cls.project.id,
        })
        cls.tower = cls.Structure.create({
            'project_id': cls.project.id,
            'subzone_id': cls.subzone.id,
            'structure_level': 'item',
            'structure_type': 'tower',
            'name': 'Tower E1',
            'code': 'TE1',
        })
        cls.basement = cls.Structure.create({
            'project_id': cls.project.id,
            'subzone_id': cls.subzone.id,
            'structure_level': 'sub_item',
            'structure_type': 'basement',
            'parent_id': cls.tower.id,
            'name': 'Tầng hầm Tower E1',
            'code': 'TE1_HAM',
        })
        # Pick a few seeded categories on this project
        cls.cat_foundation = cls.Category.search([
            ('project_id', '=', cls.project.id),
            ('code', '=', 'MONG'),
        ], limit=1)
        cls.cat_structure = cls.Category.search([
            ('project_id', '=', cls.project.id),
            ('code', '=', 'KCT'),
        ], limit=1)

    def test_create_line(self):
        line = self.Line.create({
            'structure_id': self.basement.id,
            'category_id': self.cat_foundation.id,
            'amount': 5_000_000_000,
            'description': 'Cọc khoan nhồi D800',
        })
        self.assertEqual(line.amount, 5_000_000_000)
        self.assertEqual(line.project_id, self.project)
        self.assertEqual(line.subzone_id, self.subzone)
        self.assertEqual(line.parent_structure_id, self.tower)

    def test_estimate_total_computed(self):
        self.Line.create({
            'structure_id': self.basement.id,
            'category_id': self.cat_foundation.id,
            'amount': 5_000_000_000,
        })
        self.Line.create({
            'structure_id': self.basement.id,
            'category_id': self.cat_structure.id,
            'amount': 3_200_000_000,
        })
        self.basement.invalidate_recordset(['estimate_total'])
        self.assertEqual(self.basement.estimate_total, 8_200_000_000)

    def test_unique_category_per_structure(self):
        self.Line.create({
            'structure_id': self.basement.id,
            'category_id': self.cat_foundation.id,
            'amount': 1_000_000_000,
        })
        with self.assertRaises(Exception):  # UNIQUE constraint
            self.Line.create({
                'structure_id': self.basement.id,
                'category_id': self.cat_foundation.id,
                'amount': 2_000_000_000,
            })

    def test_category_must_match_project(self):
        """Category from another project should be rejected."""
        other_project = self.env['re.project'].create({
            'name': 'Other Project',
            'code': 'OTH',
            'development_type': 'low_rise',
        })
        other_cat = self.Category.search([
            ('project_id', '=', other_project.id),
            ('code', '=', 'MONG'),
        ], limit=1)
        self.assertTrue(other_cat, 'Other project should have seeded MONG category')

        with self.assertRaises(ValidationError):
            self.Line.create({
                'structure_id': self.basement.id,
                'category_id': other_cat.id,
                'amount': 1_000_000_000,
            })

    def test_amount_negative_fails(self):
        with self.assertRaises(ValidationError):
            self.Line.create({
                'structure_id': self.basement.id,
                'category_id': self.cat_foundation.id,
                'amount': -1_000_000_000,
            })

    def test_amount_zero_ok(self):
        """Zero amount is allowed (placeholder for future entry)."""
        line = self.Line.create({
            'structure_id': self.basement.id,
            'category_id': self.cat_foundation.id,
            'amount': 0,
            'description': 'TBD',
        })
        self.assertEqual(line.amount, 0)

    def test_cascade_delete_with_structure(self):
        line = self.Line.create({
            'structure_id': self.basement.id,
            'category_id': self.cat_foundation.id,
            'amount': 1_000_000_000,
        })
        line_id = line.id
        self.basement.unlink()
        # Line should be deleted by CASCADE
        self.assertFalse(self.Line.browse(line_id).exists())
