# -*- coding: utf-8 -*-
"""Tests cho bridge: gói thầu → HĐ nhà thầu (P5.4)."""

from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import UserError


@tagged('post_install', '-at_install', 'realty_tender_contract')
class TestTenderContractBridge(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Package = cls.env['rp.tender.package']
        cls.Contract = cls.env['rp.contract']
        cls.Contractor = cls.env['rp.contractor']
        cls.Bidder = cls.env['rp.tender.bidder']

        cls.project = cls.env['re.project'].create({
            'name': 'Bridge Test', 'code': 'BR',
            'development_type': 'mixed',
        })
        cls.subzone = cls.env['re.subzone'].create({
            'name': 'SZ', 'code': 'SZ',
            'project_id': cls.project.id,
        })
        cls.struct = cls.env['rp.structure'].create({
            'project_id': cls.project.id,
            'subzone_id': cls.subzone.id,
            'structure_level': 'item',
            'structure_type': 'tower',
            'name': 'Tower BR1',
        })
        cls.nt_a = cls.Contractor.create({
            'name': 'NT Bridge A', 'code': 'NT-BR-A',
            'contractor_type': 'general', 'state': 'approved',
        })

        cls.pkg = cls.Package.create({
            'name': 'Bridge Package', 'code': 'PKG-BR-01',
            'project_id': cls.project.id,
            'selection_method': 'open',
            'deadline_contract': '2026-12-31',
            'max_approved_price': 1000000000.0,
            'line_ids': [(0, 0, {'structure_id': cls.struct.id})],
        })

    def _walk_to_awarded(self, contract_amount=900000000.0):
        """Helper: đi từ draft → awarded để test action_contract."""
        self.pkg.action_approve_plan()
        self.pkg.action_invite()
        self.pkg.action_close_bid()
        self.pkg.action_evaluate()
        self.pkg.action_negotiate()
        # Tạo bidder + chọn winner
        b = self.Bidder.create({
            'package_id': self.pkg.id,
            'contractor_id': self.nt_a.id,
            'price_offered': contract_amount,
            'technical_score': 85.0,
        })
        b.action_select_as_winner()
        self.pkg.action_award()
        # Set contract_amount riêng (mặc định = award_amount qua onchange,
        # ở đây test direct create nên gán tay)
        self.pkg.contract_amount = contract_amount

    def test_action_contract_creates_draft(self):
        """awarded → action_contract → tạo rp.contract draft."""
        self._walk_to_awarded()
        self.assertFalse(self.pkg.contract_ids)

        self.pkg.action_contract()
        self.assertEqual(self.pkg.state, 'contracted')
        self.assertEqual(self.pkg.contract_count, 1)

        hd = self.pkg.contract_ids[0]
        self.assertEqual(hd.state, 'draft')
        self.assertEqual(hd.tender_package_id, self.pkg)
        self.assertEqual(hd.contractor_id, self.nt_a.partner_id)
        self.assertEqual(hd.contract_value_pretax, 900000000.0)
        self.assertEqual(hd.name, 'PKG-BR-01-HD')
        self.assertEqual(hd.contract_date, self.pkg.date_award_signed)

    def test_action_contract_idempotent(self):
        """Đã có HĐ → gọi action_contract lần 2 không tạo trùng."""
        self._walk_to_awarded()
        self.pkg.action_contract()
        self.assertEqual(self.pkg.contract_count, 1)

        # Reset về awarded để test idempotent
        self.pkg.state = 'awarded'
        self.pkg.action_contract()
        self.assertEqual(self.pkg.contract_count, 1)
        self.assertEqual(self.pkg.state, 'contracted')

    def test_action_contract_fallback_name(self):
        """Gói thầu không có code → name = 'HD-PKG{id}'."""
        pkg2 = self.Package.create({
            'name': 'No Code Package',
            'project_id': self.project.id,
            'selection_method': 'designated',
            'deadline_contract': '2026-12-31',
            'max_approved_price': 500000000.0,
            'contractor_id': self.nt_a.partner_id.id,
            'award_amount': 400000000.0,
            'contract_amount': 400000000.0,
            'state': 'awarded',
            'date_award_signed': '2026-06-01',
            'line_ids': [(0, 0, {'structure_id': self.struct.id})],
        })
        pkg2.action_contract()
        self.assertEqual(pkg2.contract_count, 1)
        self.assertEqual(pkg2.contract_ids[0].name, f'HD-PKG{pkg2.id}')

    def test_action_contract_blocks_no_amount(self):
        """Thiếu contract_amount → UserError."""
        pkg3 = self.Package.create({
            'name': 'No Amount',
            'project_id': self.project.id,
            'selection_method': 'open',
            'deadline_contract': '2026-12-31',
            'max_approved_price': 1000000000.0,
            'contractor_id': self.nt_a.partner_id.id,
            'state': 'awarded',
            'line_ids': [(0, 0, {'structure_id': self.struct.id})],
        })
        with self.assertRaises(UserError):
            pkg3.action_contract()

    def test_primary_contract_id_compute(self):
        """primary_contract_id = HĐ đầu tiên (sorted by id desc default)."""
        self._walk_to_awarded()
        self.pkg.action_contract()
        primary = self.pkg.primary_contract_id
        self.assertEqual(primary, self.pkg.contract_ids[0])
