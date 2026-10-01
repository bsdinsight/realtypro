# -*- coding: utf-8 -*-
"""Việc 1425/1429 — một mục đích gắn MỘT dự án.

Khai dự án ở đầu mục đích thì bảng phân bổ phải tự có đúng một dòng
bằng trọn hạn mức: toàn bộ trục dự án (dư nợ theo dự án, khả dụng,
tab "Hạn mức theo dự án" trên HĐTD) đọc từ bảng đó, bảng rỗng là mọi
báo cáo theo dự án trống.
"""
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 're_loan')
class TestFacilitySingleProject(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bank = cls.env['res.partner'].create({
            'name': 'NH Test 1425', 'is_company': True, 'is_bank': True})
        cls.contract = cls.env['re.loan.credit.contract'].create({
            'name': 'HĐTD-1425', 'partner_id': cls.bank.id,
            'amount_total': 1_000_000_000.0})
        cls.project_a = cls.env['re.project'].create(
            {'name': 'Dự án A', 'code': 'DA-1425-A'})
        cls.project_b = cls.env['re.project'].create(
            {'name': 'Dự án B', 'code': 'DA-1425-B'})

    def _facility(self, **vals):
        base = {
            'name': 'Mục đích 1425',
            'credit_contract_id': self.contract.id,
            'facility_type': 'term',
            'amount_limit': 500_000_000.0,
        }
        base.update(vals)
        return self.env['re.loan.facility'].create(base)

    def test_project_creates_allocation(self):
        fac = self._facility(project_id=self.project_a.id)
        self.assertEqual(len(fac.project_allocation_ids), 1)
        self.assertEqual(fac.project_allocation_ids.project_id,
                         self.project_a)
        self.assertEqual(fac.project_allocation_ids.amount,
                         500_000_000.0)
        self.assertEqual(fac.amount_unallocated, 0.0)

    def test_limit_change_follows(self):
        fac = self._facility(project_id=self.project_a.id)
        fac.amount_limit = 700_000_000.0
        self.assertEqual(fac.project_allocation_ids.amount,
                         700_000_000.0)
        self.assertEqual(fac.amount_unallocated, 0.0)

    def test_switch_project_moves_allocation(self):
        fac = self._facility(project_id=self.project_a.id)
        fac.project_id = self.project_b
        self.assertEqual(len(fac.project_allocation_ids), 1)
        self.assertEqual(fac.project_allocation_ids.project_id,
                         self.project_b)

    def test_multi_allocation_blocks_single_project(self):
        """Đang chia cho hai dự án thì không cho khai một dự án duy
        nhất — hệ thống không tự quyết hộ phần của ai bị xoá."""
        fac = self._facility()
        self.env['re.loan.facility.project.allocation'].create([
            {'facility_id': fac.id, 'project_id': self.project_a.id,
             'amount': 300_000_000.0},
            {'facility_id': fac.id, 'project_id': self.project_b.id,
             'amount': 200_000_000.0},
        ])
        with self.assertRaises(ValidationError):
            fac.project_id = self.project_a

    def test_no_project_keeps_manual_table(self):
        fac = self._facility()
        self.assertFalse(fac.project_allocation_ids)
        self.env['re.loan.facility.project.allocation'].create({
            'facility_id': fac.id, 'project_id': self.project_a.id,
            'amount': 100_000_000.0})
        fac.amount_limit = 600_000_000.0
        # Không có dự án đơn → hệ thống KHÔNG đụng vào bảng phân bổ.
        self.assertEqual(fac.project_allocation_ids.amount,
                         100_000_000.0)
