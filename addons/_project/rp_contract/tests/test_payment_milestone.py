# -*- coding: utf-8 -*-
"""Tests rp.contract.payment.milestone — % / amount / paid lifecycle."""
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'rp_contract')
class TestPaymentMilestone(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.project = cls.env['re.project'].create({'name': 'Proj-PM', 'code': 'PM'})
        cls.subzone = cls.env['re.subzone'].create({
            'name': 'SZ-PM', 'project_id': cls.project.id, 'code': 'SZ'})
        cls.structure = cls.env['rp.structure'].create({
            'name': 'Tower-PM', 'project_id': cls.project.id,
            'subzone_id': cls.subzone.id,
            'structure_level': 'item', 'structure_type': 'tower'})
        cls.contractor = cls.env['res.partner'].create({
            'is_contractor': True, 'is_company': True,
            'name': 'NT-PM', 'ref': 'NT-PM'})
        cls.package = cls.env['rp.tender.package'].create({
            'name': 'Pkg-PM', 'project_id': cls.project.id, 'code': 'SZ'})
        cls.env['rp.tender.package.line'].create({
            'package_id': cls.package.id,
            'structure_id': cls.structure.id})
        cls.contract = cls.env['rp.contract'].create({
            'name': 'HD-PM', 'tender_package_id': cls.package.id,
            'contractor_id': cls.contractor.id,
            'contract_value_pretax': 1_000_000_000.0,
            'vat_rate': 8.0})
        cls.contract.action_sign()

    def _milestone(self, name, percent=0.0, amount=None):
        vals = {'contract_id': self.contract.id, 'name': name,
                'percent': percent}
        if amount is not None:
            vals['amount'] = amount
        return self.env['rp.contract.payment.milestone'].create(vals)

    def test_percent_computes_amount(self):
        m = self._milestone('Tạm ứng 30%', percent=30.0)
        # 30% × 1,080,000,000 = 324,000,000
        self.assertAlmostEqual(m.amount, 324_000_000.0, delta=1)

    def test_paid_rolls_up(self):
        m1 = self._milestone('Đợt 1', percent=40.0)
        m2 = self._milestone('Đợt 2', percent=50.0)
        self.assertEqual(self.contract.amount_paid, 0)
        m1.action_set_paid()
        self.assertAlmostEqual(self.contract.amount_paid,
                               432_000_000.0, delta=1)
        m2.action_set_paid()
        self.assertAlmostEqual(self.contract.amount_paid,
                               972_000_000.0, delta=1)
        self.assertAlmostEqual(self.contract.payment_progress, 90.0, delta=0.1)

    def test_total_percent_max_100(self):
        self._milestone('M1', percent=60.0)
        with self.assertRaises(ValidationError):
            self._milestone('M2', percent=50.0)  # 60 + 50 > 100

    def test_lifecycle(self):
        m = self._milestone('M', percent=10.0)
        self.assertEqual(m.state, 'planned')
        m.action_set_invoiced()
        self.assertEqual(m.state, 'invoiced')
        m.action_set_paid()
        self.assertEqual(m.state, 'paid')
        self.assertTrue(m.paid_date)
