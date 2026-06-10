# -*- coding: utf-8 -*-
"""
Tests for re.partner.relationship and the Buyer/Co-owner field additions
on res.partner (vn_permanent_address, relationship_ids O2M).
"""
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 're_party')
class TestPartnerRelationship(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Partner = cls.env['res.partner']
        cls.husband = Partner.create({
            'name': 'Nguyễn Văn A',
            'vn_national_id': '012345678901',  # 12-digit CCCD
        })
        cls.wife = Partner.create({
            'name': 'Trần Thị B',
            'vn_national_id': '098765432109',
        })
        cls.child = Partner.create({
            'name': 'Nguyễn Văn C',
        })

    # ----- Basic CRUD -----------------------------------------------------
    def test_create_spouse_relationship(self):
        rel = self.env['re.partner.relationship'].create({
            'partner_id': self.husband.id,
            'related_partner_id': self.wife.id,
            'relationship_type': 'spouse',
        })
        self.assertEqual(rel.partner_id, self.husband)
        self.assertEqual(rel.related_partner_id, self.wife)
        self.assertEqual(rel.relationship_type, 'spouse')
        self.assertIn('Nguyễn Văn A', rel.display_name)
        self.assertIn('Trần Thị B', rel.display_name)
        self.assertIn('Vợ/Chồng', rel.display_name)

    def test_relationship_visible_via_o2m(self):
        self.env['re.partner.relationship'].create({
            'partner_id': self.husband.id,
            'related_partner_id': self.wife.id,
            'relationship_type': 'spouse',
        })
        self.env['re.partner.relationship'].create({
            'partner_id': self.husband.id,
            'related_partner_id': self.child.id,
            'relationship_type': 'child',
        })
        self.assertEqual(len(self.husband.relationship_ids), 2)
        types = set(self.husband.relationship_ids.mapped('relationship_type'))
        self.assertEqual(types, {'spouse', 'child'})

    # ----- Constraints ----------------------------------------------------
    def test_cannot_relate_to_self(self):
        with self.assertRaises(ValidationError):
            self.env['re.partner.relationship'].create({
                'partner_id': self.husband.id,
                'related_partner_id': self.husband.id,
                'relationship_type': 'other',
            })

    def test_unique_pair(self):
        self.env['re.partner.relationship'].create({
            'partner_id': self.husband.id,
            'related_partner_id': self.wife.id,
            'relationship_type': 'spouse',
        })
        # Second relationship for the same pair must fail, regardless of
        # the type used.
        with self.assertRaises(Exception):
            self.env['re.partner.relationship'].create({
                'partner_id': self.husband.id,
                'related_partner_id': self.wife.id,
                'relationship_type': 'other',
            })

    def test_inverse_pair_allowed(self):
        # Symmetry is manual: A→B and B→A must BOTH be creatable so the
        # user can declare the inverse explicitly when desired.
        self.env['re.partner.relationship'].create({
            'partner_id': self.husband.id,
            'related_partner_id': self.wife.id,
            'relationship_type': 'spouse',
        })
        inverse = self.env['re.partner.relationship'].create({
            'partner_id': self.wife.id,
            'related_partner_id': self.husband.id,
            'relationship_type': 'spouse',
        })
        self.assertTrue(inverse.id)

    def test_cascade_on_partner_unlink(self):
        rel = self.env['re.partner.relationship'].create({
            'partner_id': self.husband.id,
            'related_partner_id': self.wife.id,
            'relationship_type': 'spouse',
        })
        rel_id = rel.id
        self.husband.unlink()
        self.assertFalse(
            self.env['re.partner.relationship'].browse(rel_id).exists()
        )

    def test_restrict_on_related_partner_unlink(self):
        self.env['re.partner.relationship'].create({
            'partner_id': self.husband.id,
            'related_partner_id': self.wife.id,
            'relationship_type': 'spouse',
        })
        # related_partner_id is ondelete='restrict' — cannot remove the
        # wife while she is a referenced related_partner.
        with self.assertRaises(Exception):
            self.wife.unlink()

    # ----- vn_permanent_address ------------------------------------------
    def test_permanent_address_persists(self):
        addr = ('Số 123 đường Nguyễn Văn A, '
                'Phường Bến Nghé, TP Hồ Chí Minh')
        self.husband.vn_permanent_address = addr
        self.husband.flush_recordset()
        self.husband.invalidate_recordset()
        self.assertEqual(self.husband.vn_permanent_address, addr)

    def test_permanent_address_optional(self):
        # Field is not required; partners without it must still validate.
        p = self.env['res.partner'].create({'name': 'No Address'})
        self.assertFalse(p.vn_permanent_address)
