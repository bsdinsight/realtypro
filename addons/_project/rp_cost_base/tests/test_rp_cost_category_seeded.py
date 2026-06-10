# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install', 'realty_cost_base')
class TestCostCategorySeeded(TransactionCase):
    """When a re.project is created, the Vietnamese default cost
    category tree should be auto-seeded on it.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Category = cls.env['rp.cost.category']
        cls.project = cls.env['re.project'].create({
            'name': 'Seed Test Project',
            'code': 'STP',
            'development_type': 'high_rise',
        })

    def test_total_seeded(self):
        """Project should have 83 categories: 11 L1 + 72 L2."""
        cats = self.Category.search([('project_id', '=', self.project.id)])
        self.assertEqual(len(cats), 83,
                         f'Expected 83 categories, got {len(cats)}')

    def test_l1_count(self):
        """11 categories at level 1."""
        l1 = self.Category.search([
            ('project_id', '=', self.project.id),
            ('parent_id', '=', False),
        ])
        self.assertEqual(len(l1), 11)

    def test_l2_count(self):
        """72 categories at level 2."""
        l2 = self.Category.search([
            ('project_id', '=', self.project.id),
            ('level', '=', 2),
        ])
        self.assertEqual(len(l2), 72)

    def test_contingency_flagged(self):
        """Category 11 'Dự phòng' and its children flagged as contingency."""
        cat11 = self.Category.search([
            ('project_id', '=', self.project.id),
            ('code', '=', '11'),
        ], limit=1)
        self.assertTrue(cat11.is_contingency, 'Category 11 (Dự phòng) should be contingency')
        children = cat11.child_ids
        for child in children:
            self.assertTrue(child.is_contingency,
                            f'{child.code} child of Dự phòng should also be contingency')

    def test_land_cost_flagged(self):
        """Category 1 'Chi phí đất' children flagged as land_cost."""
        cat1 = self.Category.search([
            ('project_id', '=', self.project.id),
            ('code', '=', '1'),
        ], limit=1)
        self.assertTrue(cat1.is_land_cost)
        # 1.1, 1.2, 1.3, 1.4 are land cost; 1.5, 1.6 are not
        cat_1_1 = self.Category.search([
            ('project_id', '=', self.project.id),
            ('code', '=', '1.1'),
        ], limit=1)
        self.assertTrue(cat_1_1.is_land_cost)
        cat_1_5 = self.Category.search([
            ('project_id', '=', self.project.id),
            ('code', '=', '1.5'),
        ], limit=1)
        self.assertFalse(cat_1_5.is_land_cost)

    def test_path_computed(self):
        """complete_path of an L2 category includes parent name."""
        cat = self.Category.search([
            ('project_id', '=', self.project.id),
            ('code', '=', '3.2'),
        ], limit=1)
        self.assertIn('Chi phí xây dựng công trình', cat.complete_path)
        self.assertIn('Móng', cat.complete_path)

    def test_seed_idempotent(self):
        """Re-running seed on already-seeded project = no-op."""
        self.Category._seed_defaults_for_project(self.project)
        cats = self.Category.search([('project_id', '=', self.project.id)])
        self.assertEqual(len(cats), 83,
                         'Idempotent seed should not duplicate.')

    def test_user_edit_survives_idempotent_seed(self):
        """User-edited category survives a re-run of the seed."""
        cat = self.Category.search([
            ('project_id', '=', self.project.id),
            ('code', '=', '3'),
        ], limit=1)
        cat.name = 'Chi phí xây dựng (edited by user)'
        # Run seed again — should not touch existing
        self.Category._seed_defaults_for_project(self.project)
        cat.invalidate_recordset()
        self.assertEqual(cat.name, 'Chi phí xây dựng (edited by user)')
