# -*- coding: utf-8 -*-
"""Tests for rp.structure lifecycle and constraint enforcement (v1.4.3-r4).

Two structure_level values: item, sub_item. Common Cost was removed in r4.
"""

from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import ValidationError


@tagged('post_install', '-at_install', 'realty_cost_base')
class TestRpStructureLifecycle(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Structure = cls.env['rp.structure']
        cls.project = cls.env['re.project'].create({
            'name': 'Structure Test Project',
            'code': 'STX',
            'development_type': 'mixed',
        })
        cls.subzone = cls.env['re.subzone'].create({
            'name': 'Test Subzone S1',
            'code': 'S1',
            'project_id': cls.project.id,
        })
        cls.other_subzone = cls.env['re.subzone'].create({
            'name': 'Test Subzone S2',
            'code': 'S2',
            'project_id': cls.project.id,
        })

    # ----- Happy path: item under subzone

    def test_create_item_under_subzone(self):
        item = self.Structure.create({
            'project_id': self.project.id,
            'subzone_id': self.subzone.id,
            'structure_level': 'item',
            'structure_type': 'tower',
            'name': 'Tower T1',
            'code': 'T1',
        })
        self.assertEqual(item.structure_level, 'item')
        self.assertEqual(item.subzone_id, self.subzone)
        self.assertFalse(item.parent_id)

    # ----- Happy path: sub_item under item

    def test_create_sub_item_under_item(self):
        item = self.Structure.create({
            'project_id': self.project.id,
            'subzone_id': self.subzone.id,
            'structure_level': 'item',
            'structure_type': 'tower',
            'name': 'Tower T2',
        })
        sub = self.Structure.create({
            'project_id': self.project.id,
            'subzone_id': self.subzone.id,
            'parent_id': item.id,
            'structure_level': 'sub_item',
            'structure_type': 'basement',
            'name': 'Tầng hầm T2',
        })
        self.assertEqual(sub.parent_id, item)
        self.assertEqual(sub.subzone_id, item.subzone_id)

    # ----- Constraint: sub_item without parent — fail

    def test_sub_item_without_parent_fails(self):
        with self.assertRaises(ValidationError):
            self.Structure.create({
                'project_id': self.project.id,
                'subzone_id': self.subzone.id,
                'structure_level': 'sub_item',
                'structure_type': 'foundation',
                'name': 'Orphan Sub',
            })

    # ----- Constraint: sub_item under sub_item — fail (3rd level not allowed)

    def test_sub_item_under_sub_item_fails(self):
        item = self.Structure.create({
            'project_id': self.project.id,
            'subzone_id': self.subzone.id,
            'structure_level': 'item',
            'structure_type': 'tower',
            'name': 'Tower T3',
        })
        sub = self.Structure.create({
            'project_id': self.project.id,
            'subzone_id': self.subzone.id,
            'parent_id': item.id,
            'structure_level': 'sub_item',
            'structure_type': 'foundation',
            'name': 'T3 Foundation',
        })
        with self.assertRaises(ValidationError):
            self.Structure.create({
                'project_id': self.project.id,
                'subzone_id': self.subzone.id,
                'parent_id': sub.id,  # parent is sub_item, not item
                'structure_level': 'sub_item',
                'structure_type': 'mep',
                'name': 'Should fail',
            })

    # ----- Constraint: item without subzone — fail

    def test_item_without_subzone_fails(self):
        with self.assertRaises(ValidationError):
            self.Structure.create({
                'project_id': self.project.id,
                'structure_level': 'item',
                'structure_type': 'tower',
                'name': 'No subzone tower',
            })

    # ----- Constraint: sub_item with mismatched subzone — fail

    def test_sub_item_subzone_must_match_parent(self):
        item = self.Structure.create({
            'project_id': self.project.id,
            'subzone_id': self.subzone.id,
            'structure_level': 'item',
            'structure_type': 'tower',
            'name': 'Tower S1',
        })
        with self.assertRaises(ValidationError):
            self.Structure.create({
                'project_id': self.project.id,
                'subzone_id': self.other_subzone.id,  # mismatched!
                'parent_id': item.id,
                'structure_level': 'sub_item',
                'structure_type': 'foundation',
                'name': 'Bad sub',
            })

    # ----- Verify no common_cost level exists anymore

    def test_no_common_cost_level(self):
        """structure_level should only have item and sub_item."""
        field = self.Structure._fields['structure_level']
        keys = [k for k, _ in field.selection]
        self.assertEqual(set(keys), {'item', 'sub_item'},
            'structure_level should only allow item and sub_item in r4')

    # ----- Verify no auto-created common_cost on new projects

    def test_no_auto_common_cost_on_create(self):
        new_proj = self.env['re.project'].create({
            'name': 'Fresh Project',
            'code': 'FRESH',
            'development_type': 'low_rise',
        })
        # Search any structure on the new project — should be empty
        structures = self.Structure.search([
            ('project_id', '=', new_proj.id),
        ])
        self.assertEqual(len(structures), 0,
            'No structure should be auto-created on new project in r4')
