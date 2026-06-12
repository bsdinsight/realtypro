# -*- coding: utf-8 -*-
"""Tests cho rp.tender.bidder workflow — Phase 5.2."""

from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import ValidationError, UserError


@tagged('post_install', '-at_install', 'realty_estimate')
class TestRpTenderBidder(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Package = cls.env['rp.tender.package']
        cls.Bidder = cls.env['rp.tender.bidder']
        cls.Contractor = cls.env['rp.contractor']
        cls.Structure = cls.env['rp.structure']

        cls.project = cls.env['re.project'].create({
            'name': 'Bidder Test Project',
            'code': 'BTP',
            'development_type': 'mixed',
        })
        cls.subzone = cls.env['re.subzone'].create({
            'name': 'Subzone X', 'code': 'SZX',
            'project_id': cls.project.id,
        })
        cls.struct = cls.Structure.create({
            'project_id': cls.project.id,
            'subzone_id': cls.subzone.id,
            'structure_level': 'item',
            'structure_type': 'tower',
            'name': 'Tower X1',
        })

        # 3 approved contractors
        cls.nt_a = cls.Contractor.create({
            'name': 'Nhà thầu A', 'code': 'NT-A',
            'contractor_type': 'general',
            'state': 'approved',
        })
        cls.nt_b = cls.Contractor.create({
            'name': 'Nhà thầu B', 'code': 'NT-B',
            'contractor_type': 'general',
            'state': 'approved',
        })
        cls.nt_c = cls.Contractor.create({
            'name': 'Nhà thầu C', 'code': 'NT-C',
            'contractor_type': 'general',
            'state': 'approved',
        })
        # 1 prospect — không được tham gia
        cls.nt_prospect = cls.Contractor.create({
            'name': 'Nhà thầu Mới', 'code': 'NT-NEW',
            'contractor_type': 'general',
            'state': 'prospect',
        })

        cls.pkg = cls.Package.create({
            'name': 'Bidder Workflow Package',
            'project_id': cls.project.id,
            'selection_method': 'open',
            'deadline_contract': '2026-12-31',
            'max_approved_price': 1000000000.0,
            'line_ids': [(0, 0, {'structure_id': cls.struct.id})],
        })

    def test_ranking_by_price_lowest_first(self):
        """3 bidder giá khác nhau → ranking 1/2/3 theo giá tăng dần."""
        b_a = self.Bidder.create({
            'package_id': self.pkg.id,
            'contractor_id': self.nt_a.id,
            'price_offered': 900000000.0,
            'technical_score': 85.0,
        })
        b_b = self.Bidder.create({
            'package_id': self.pkg.id,
            'contractor_id': self.nt_b.id,
            'price_offered': 800000000.0,
            'technical_score': 80.0,
        })
        b_c = self.Bidder.create({
            'package_id': self.pkg.id,
            'contractor_id': self.nt_c.id,
            'price_offered': 850000000.0,
            'technical_score': 75.0,
        })
        # NT B rẻ nhất → rank 1
        self.assertEqual(b_b.ranking, 1)
        self.assertEqual(b_c.ranking, 2)
        self.assertEqual(b_a.ranking, 3)

    def test_disqualified_removed_from_ranking(self):
        """Bidder bị loại không tính vào ranking."""
        b_a = self.Bidder.create({
            'package_id': self.pkg.id,
            'contractor_id': self.nt_a.id,
            'price_offered': 900000000.0,
            'technical_score': 85.0,
        })
        b_b = self.Bidder.create({
            'package_id': self.pkg.id,
            'contractor_id': self.nt_b.id,
            'price_offered': 800000000.0,
            'technical_score': 80.0,
            'disqualification_reason': 'HSDT thiếu giấy phép',
        })
        b_b.action_disqualify()
        # Sau khi B bị loại, A trở thành rank 1
        self.assertEqual(b_a.ranking, 1)
        self.assertEqual(b_b.ranking, 0)

    def test_technical_pass_threshold(self):
        """Điểm KT < 70 → technical_pass = False, qualify bị block."""
        b = self.Bidder.create({
            'package_id': self.pkg.id,
            'contractor_id': self.nt_a.id,
            'technical_score': 65.0,
        })
        self.assertFalse(b.technical_pass)
        with self.assertRaises(UserError):
            b.action_qualify()

        b.technical_score = 70.0
        self.assertTrue(b.technical_pass)
        b.action_qualify()
        self.assertEqual(b.status, 'qualified')

    def test_unique_contractor_per_package(self):
        """Cùng nhà thầu nộp 2 HSDT cho 1 gói → IntegrityError."""
        self.Bidder.create({
            'package_id': self.pkg.id,
            'contractor_id': self.nt_a.id,
            'price_offered': 900000000.0,
        })
        with self.assertRaises(Exception):
            self.Bidder.create({
                'package_id': self.pkg.id,
                'contractor_id': self.nt_a.id,
                'price_offered': 950000000.0,
            })

    def test_select_winner_updates_package(self):
        """action_select_as_winner sync contractor + giá lên package."""
        b_a = self.Bidder.create({
            'package_id': self.pkg.id,
            'contractor_id': self.nt_a.id,
            'price_offered': 900000000.0,
            'technical_score': 85.0,
        })
        b_a.action_select_as_winner()
        self.assertEqual(b_a.status, 'awarded')
        self.assertEqual(self.pkg.contractor_id, self.nt_a.partner_id)
        self.assertEqual(self.pkg.award_amount, 900000000.0)
        self.assertEqual(self.pkg.awarded_bidder_id, b_a)
        # Project đã được cộng vào contractor.project_ids
        self.assertIn(self.project, self.nt_a.project_ids)

    def test_switch_winner(self):
        """Chọn winner mới → reset winner cũ về qualified."""
        b_a = self.Bidder.create({
            'package_id': self.pkg.id,
            'contractor_id': self.nt_a.id,
            'price_offered': 900000000.0,
            'technical_score': 85.0,
        })
        b_b = self.Bidder.create({
            'package_id': self.pkg.id,
            'contractor_id': self.nt_b.id,
            'price_offered': 800000000.0,
            'technical_score': 90.0,
        })
        b_a.action_select_as_winner()
        self.assertEqual(b_a.status, 'awarded')
        # Đổi winner sang B
        b_b.action_select_as_winner()
        self.assertEqual(b_b.status, 'awarded')
        self.assertEqual(b_a.status, 'qualified')
        self.assertEqual(self.pkg.contractor_id, self.nt_b.partner_id)
        self.assertEqual(self.pkg.award_amount, 800000000.0)

    def test_winner_price_above_max_blocked(self):
        """Giá dự thầu > giá trần → action_select_as_winner block."""
        b = self.Bidder.create({
            'package_id': self.pkg.id,
            'contractor_id': self.nt_a.id,
            'price_offered': 1500000000.0,
            'technical_score': 85.0,
        })
        with self.assertRaises(UserError):
            b.action_select_as_winner()

    def test_award_requires_winner_when_bidders_exist(self):
        """Có bidder nhưng chưa chọn winner → action_award block."""
        self.Bidder.create({
            'package_id': self.pkg.id,
            'contractor_id': self.nt_a.id,
            'price_offered': 900000000.0,
            'technical_score': 85.0,
        })
        # Đi tới negotiating mà chưa chọn winner
        self.pkg.write({'state': 'negotiating'})
        with self.assertRaises(UserError):
            self.pkg.action_award()

    def test_disqualify_requires_reason(self):
        """Loại bidder không có lý do → block."""
        b = self.Bidder.create({
            'package_id': self.pkg.id,
            'contractor_id': self.nt_a.id,
            'price_offered': 900000000.0,
        })
        with self.assertRaises(UserError):
            b.action_disqualify()
        b.disqualification_reason = 'HSDT không hợp lệ'
        b.action_disqualify()
        self.assertEqual(b.status, 'disqualified')

    def test_technical_score_range(self):
        """Điểm KT phải 0-100."""
        with self.assertRaises(ValidationError):
            self.Bidder.create({
                'package_id': self.pkg.id,
                'contractor_id': self.nt_a.id,
                'technical_score': 150.0,
            })
