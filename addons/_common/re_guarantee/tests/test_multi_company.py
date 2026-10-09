# -*- coding: utf-8 -*-
"""Cách ly đa công ty cho chứng thư bảo lãnh.

Đúng ca tech lead bên đối tác nêu: người dùng nhóm QUẢN LÝ, nếu không
có luật bản ghi theo công ty, sẽ đọc được dữ liệu của công ty khác.
Nhóm quản lý KHÔNG vượt được ir.rule (chỉ super user mới vượt), nên
luật toàn cục là chỗ chặn duy nhất.
"""
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 're_guarantee')
class TestGuaranteeMultiCompany(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Company = cls.env['res.company']
        Users = cls.env['res.users']
        Partner = cls.env['res.partner']
        mgr_group = cls.env.ref('re_guarantee.group_guarantee_manager')

        cls.company_a = Company.create({'name': 'Công ty A (BL)'})
        cls.company_b = Company.create({'name': 'Công ty B (BL)'})
        cls.bank = Partner.create({
            'name': 'NH đa công ty', 'is_company': True, 'is_bank': True})
        cls.other = Partner.create({
            'name': 'Đối tác BL', 'is_company': True})

        # QUẢN LÝ bảo lãnh, chỉ thuộc công ty A.
        cls.mgr_a = Users.create({
            'name': 'Quản lý BL A',
            'login': 'bl_mgr_a@test.local',
            'company_id': cls.company_a.id,
            'company_ids': [(6, 0, [cls.company_a.id])],
            'group_ids': [(4, mgr_group.id)],
        })

        cls.bg_a = cls._guarantee(cls, cls.company_a, 'BL-A-01')
        cls.bg_b = cls._guarantee(cls, cls.company_b, 'BL-B-01')

    def _guarantee(self, company, name):
        return self.env['re.bank.guarantee'].with_company(company).create({
            'name': name,
            'guarantee_type': 'performance',
            'issuing_bank_partner_id': self.bank.id,
            'applicant_partner_id': company.partner_id.id,
            'beneficiary_partner_id': self.other.id,
            'date_issue': '2026-01-01',
            'date_expiry': '2026-12-31',
            'amount': 1_000_000_000.0,
            'company_id': company.id,
        })

    def test_manager_sees_only_own_company(self):
        seen = self.env['re.bank.guarantee'].with_user(self.mgr_a).search([])
        self.assertIn(self.bg_a, seen)
        self.assertNotIn(self.bg_b, seen,
                         'quản lý công ty A đọc được chứng thư công ty B')

    def test_manager_cannot_read_other_company_directly(self):
        with self.assertRaises(AccessError):
            self.bg_b.with_user(self.mgr_a).read(['name'])

    def test_manager_cannot_write_other_company(self):
        with self.assertRaises(AccessError):
            self.bg_b.with_user(self.mgr_a).write({'amount': 1.0})

    def test_switcher_widens_view(self):
        """Được gán cả hai công ty thì nhìn được cả hai — luật bám
        `company_ids` của phiên, không ghim cứng company_id."""
        self.mgr_a.write({
            'company_ids': [(6, 0, [self.company_a.id, self.company_b.id])]})
        seen = self.env['re.bank.guarantee'].with_user(self.mgr_a).with_context(
            allowed_company_ids=[self.company_a.id, self.company_b.id]).search([])
        self.assertIn(self.bg_a, seen)
        self.assertIn(self.bg_b, seen)
