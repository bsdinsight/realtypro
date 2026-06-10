# -*- coding: utf-8 -*-
"""Tests rp.contract.amendment — 6 types + apply + audit."""
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'rp_contract')
class TestContractAmendment(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.project = cls.env['re.project'].create({'name': 'Proj-AM', 'code': 'AM'})
        cls.subzone = cls.env['re.subzone'].create({
            'name': 'SZ-AM', 'project_id': cls.project.id, 'code': 'SZ'})
        cls.structure = cls.env['rp.structure'].create({
            'name': 'T-AM', 'project_id': cls.project.id,
            'subzone_id': cls.subzone.id,
            'structure_level': 'item', 'structure_type': 'tower'})
        cls.contractor = cls.env['res.partner'].create({
            'is_contractor': True, 'is_company': True,
            'name': 'NT-AM', 'ref': 'NT-AM'})
        cls.package = cls.env['rp.tender.package'].create({
            'name': 'Pkg-AM', 'project_id': cls.project.id, 'code': 'SZ'})
        cls.env['rp.tender.package.line'].create({
            'package_id': cls.package.id,
            'structure_id': cls.structure.id})
        cls.contract = cls.env['rp.contract'].create({
            'name': 'HD-AM', 'tender_package_id': cls.package.id,
            'contractor_id': cls.contractor.id,
            'contract_value_pretax': 1_000_000_000.0,
            'date_end': '2026-12-31'})
        cls.contract.action_sign()

    def _amend(self, atype, **vals):
        return self.env['rp.contract.amendment'].create({
            'name': 'PL-' + atype, 'contract_id': self.contract.id,
            'amendment_type': atype, 'description': 'desc', **vals})

    def test_extension(self):
        am = self._amend('extension', new_date_end='2027-06-30')
        am.action_apply()
        self.assertEqual(str(self.contract.date_end), '2027-06-30')
        self.assertEqual(am.state, 'applied')

    def test_value_change(self):
        am = self._amend('value', new_contract_value_pretax=1_500_000_000.0)
        am.action_apply()
        self.assertEqual(self.contract.contract_value_pretax, 1_500_000_000.0)
        self.assertEqual(am.value_old, '1,000,000,000')
        self.assertEqual(am.value_new, '1,500,000,000')

    def test_scope_records_description(self):
        am = self._amend('scope', description='Mở rộng phạm vi MEP tầng 5')
        am.action_apply()
        self.assertEqual(am.state, 'applied')

    def test_cannot_apply_twice(self):
        am = self._amend('extension', new_date_end='2027-06-30')
        am.action_apply()
        with self.assertRaises(UserError):
            am.action_apply()

    def test_cannot_unlink_applied(self):
        am = self._amend('extension', new_date_end='2027-06-30')
        am.action_apply()
        with self.assertRaises(UserError):
            am.unlink()

    def test_cannot_apply_on_draft_contract(self):
        draft = self.env['rp.contract'].create({
            'name': 'HD-Draft', 'tender_package_id': self.package.id,
            'contractor_id': self.contractor.id,
            'contract_value_pretax': 500_000_000.0})
        am = self.env['rp.contract.amendment'].create({
            'name': 'PL-x', 'contract_id': draft.id,
            'amendment_type': 'extension', 'description': '...',
            'new_date_end': '2027-06-30'})
        with self.assertRaises(UserError):
            am.action_apply()
