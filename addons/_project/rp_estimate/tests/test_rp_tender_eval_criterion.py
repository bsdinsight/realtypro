# -*- coding: utf-8 -*-
"""Tests cho rp.tender.eval.criterion + HSMT content — Phase 5.3."""

from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import ValidationError


@tagged('post_install', '-at_install', 'realty_estimate')
class TestRpTenderEvalCriterion(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Package = cls.env['rp.tender.package']
        cls.Criterion = cls.env['rp.tender.eval.criterion']

        cls.project = cls.env['re.project'].create({
            'name': 'Eval Test Project', 'code': 'ETP',
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
            'name': 'Tower Test',
        })
        cls.pkg = cls.Package.create({
            'name': 'Eval Pkg',
            'project_id': cls.project.id,
            'line_ids': [(0, 0, {'structure_id': cls.struct.id})],
        })

    def test_create_3_kinds(self):
        """Tạo 3 criteria thuộc 3 nhóm: capacity, technical, price."""
        c1 = self.Criterion.create({
            'package_id': self.pkg.id,
            'kind': 'capacity',
            'name': 'Số năm hoạt động',
            'weight': 30.0,
        })
        c2 = self.Criterion.create({
            'package_id': self.pkg.id,
            'kind': 'technical',
            'name': 'Biện pháp thi công',
            'weight': 40.0,
        })
        c3 = self.Criterion.create({
            'package_id': self.pkg.id,
            'kind': 'price',
            'name': 'Giá thấp nhất',
            'weight': 100.0,
        })
        self.assertEqual(self.pkg.eval_criterion_count, 3)
        self.assertIn(c1, self.pkg.eval_criterion_ids)
        self.assertIn(c2, self.pkg.eval_criterion_ids)
        self.assertIn(c3, self.pkg.eval_criterion_ids)

    def test_seed_default_criteria(self):
        """action_seed_default_criteria tạo bộ chuẩn VN."""
        self.assertEqual(self.pkg.eval_criterion_count, 0)
        self.pkg.action_seed_default_criteria()
        self.assertEqual(self.pkg.eval_criterion_count, 8)
        # 4 capacity + 3 technical + 1 price
        by_kind = {k: 0 for k in ['capacity', 'technical', 'price']}
        for c in self.pkg.eval_criterion_ids:
            by_kind[c.kind] += 1
        self.assertEqual(by_kind, {
            'capacity': 4, 'technical': 3, 'price': 1})
        # Idempotent: gọi lần 2 không tạo thêm
        self.pkg.action_seed_default_criteria()
        self.assertEqual(self.pkg.eval_criterion_count, 8)

    def test_weight_must_be_non_negative(self):
        with self.assertRaises(ValidationError):
            self.Criterion.create({
                'package_id': self.pkg.id,
                'kind': 'capacity',
                'name': 'Bad weight',
                'weight': -5.0,
            })

    def test_html_fields_persist(self):
        """instructions_html + technical_requirements_html lưu OK."""
        self.pkg.write({
            'instructions_html': '<p>Hướng dẫn nhà thầu.</p>',
            'technical_requirements_html': '<p>Yêu cầu KT.</p>',
        })
        self.assertIn('Hướng dẫn', self.pkg.instructions_html)
        self.assertIn('Yêu cầu', self.pkg.technical_requirements_html)

    def test_hsmt_attachment(self):
        """Upload tài liệu HSMT — M2M ir.attachment."""
        att = self.env['ir.attachment'].create({
            'name': 'HSMT.pdf',
            'datas': b'JVBERi0xLjQK',  # dummy PDF header base64
        })
        self.pkg.hsmt_attachment_ids = [(4, att.id)]
        self.assertEqual(self.pkg.hsmt_attachment_count, 1)
        self.assertIn(att, self.pkg.hsmt_attachment_ids)

    def test_cascade_delete_criteria_with_package(self):
        """Xóa package → cascade xóa criteria."""
        self.Criterion.create({
            'package_id': self.pkg.id,
            'kind': 'capacity',
            'name': 'X',
        })
        crit_id = self.pkg.eval_criterion_ids[0].id
        self.pkg.unlink()
        self.assertFalse(self.Criterion.search([('id', '=', crit_id)]))
