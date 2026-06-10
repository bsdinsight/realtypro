# -*- coding: utf-8 -*-
"""
Tests for the Phase 4.0a sale-activity gating fields:
- is_open_for_sale on re.project, re.subzone, re.building
- effective_open_for_sale rollup on re.unit
"""
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 're_base', 'phase_4_0a')
class TestOpenForSaleRollup(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.project = cls.env['re.project'].create({
            'name': 'Test Project',
            'code': 'TP01',
            'development_type': 'high_rise',
        })
        cls.project_with_subzone = cls.env['re.project'].create({
            'name': 'Mega Project',
            'code': 'MP01',
            'development_type': 'mixed',
        })
        cls.subzone = cls.env['re.subzone'].create({
            'name': 'Subzone A',
            'code': 'SA',
            'project_id': cls.project_with_subzone.id,
        })
        cls.unit_type = cls.env['re.unit.type'].search([], limit=1)
        if not cls.unit_type:
            cls.unit_type = cls.env['re.unit.type'].create({
                'name': 'Test Type', 'code': 'TT',
            })

    def _make_unit(self, project, subzone=None):
        building = self.env['re.building'].create({
            'name': 'B-' + project.code,
            'code': 'B-' + project.code,
            'project_id': project.id,
            'subzone_id': subzone.id if subzone else False,
        })
        floor = self.env['re.floor'].create({
            'name': 'F1',
            'code': 'F1-' + project.code,
            'building_id': building.id,
            'floor_number': 1,
        })
        unit = self.env['re.unit'].create({
            'unit_code': 'U-' + project.code,
            'project_id': project.id,
            'building_id': building.id,
            'floor_id': floor.id,
            'unit_type_id': self.unit_type.id,
        })
        return unit, building, floor

    # ----- Defaults -------------------------------------------------------
    def test_default_is_false_on_new_records(self):
        """New entities default to is_open_for_sale=False (explicit opt-in)."""
        p = self.env['re.project'].create({
            'name': 'New', 'code': 'NEW', 'development_type': 'high_rise',
        })
        self.assertFalse(p.is_open_for_sale)
        b = self.env['re.building'].create({
            'name': 'NB', 'code': 'NB', 'project_id': p.id,
        })
        self.assertFalse(b.is_open_for_sale)
        s = self.env['re.subzone'].create({
            'name': 'NS', 'code': 'NS', 'project_id': p.id,
        })
        self.assertFalse(s.is_open_for_sale)

    # ----- Effective rollup without subzone ------------------------------
    def test_effective_false_when_project_off(self):
        unit, building, _ = self._make_unit(self.project)
        building.is_open_for_sale = True
        self.project.is_open_for_sale = False
        unit.invalidate_recordset(['effective_open_for_sale'])
        self.assertFalse(unit.effective_open_for_sale)

    def test_effective_false_when_building_off(self):
        unit, building, _ = self._make_unit(self.project)
        self.project.is_open_for_sale = True
        building.is_open_for_sale = False
        unit.invalidate_recordset(['effective_open_for_sale'])
        self.assertFalse(unit.effective_open_for_sale)

    def test_effective_true_when_both_on_no_subzone(self):
        unit, building, _ = self._make_unit(self.project)
        self.project.is_open_for_sale = True
        building.is_open_for_sale = True
        unit.invalidate_recordset(['effective_open_for_sale'])
        self.assertTrue(unit.effective_open_for_sale)

    # ----- Effective rollup WITH subzone ---------------------------------
    def test_effective_with_subzone_all_on(self):
        unit, building, _ = self._make_unit(self.project_with_subzone, self.subzone)
        self.project_with_subzone.is_open_for_sale = True
        self.subzone.is_open_for_sale = True
        building.is_open_for_sale = True
        unit.invalidate_recordset(['effective_open_for_sale'])
        self.assertTrue(unit.effective_open_for_sale)

    def test_effective_with_subzone_off(self):
        unit, building, _ = self._make_unit(self.project_with_subzone, self.subzone)
        self.project_with_subzone.is_open_for_sale = True
        self.subzone.is_open_for_sale = False
        building.is_open_for_sale = True
        unit.invalidate_recordset(['effective_open_for_sale'])
        self.assertFalse(unit.effective_open_for_sale)

    # ----- Reactivity to upstream toggle ---------------------------------
    def test_toggling_project_propagates(self):
        unit, building, _ = self._make_unit(self.project)
        self.project.is_open_for_sale = True
        building.is_open_for_sale = True
        unit.invalidate_recordset(['effective_open_for_sale'])
        self.assertTrue(unit.effective_open_for_sale)
        # Now toggle project off — unit's effective must follow.
        self.project.is_open_for_sale = False
        unit.invalidate_recordset(['effective_open_for_sale'])
        self.assertFalse(unit.effective_open_for_sale)
