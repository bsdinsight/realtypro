# -*- coding: utf-8 -*-
"""Việc con của task 1081 "Dự thầu" — phần sửa không cần chốt thiết kế.

1403  nhân bản công bố giá: không đụng ràng buộc số + ngày, và CHÉP dòng giá
1396  bảng giá gói: ô chọn ẩn item đã khai
1101  nút Xem ở đầu dòng mở dòng BoQ / hạng mục toàn trang
1381  (vế "phải F5 mới thấy") thông báo xong thì nạp lại màn hình
"""
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'rp_bid')
class TestTask1081(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        unit = env.ref('uom.product_uom_unit')
        Res = env['rp.resource']
        cls.cement = Res.create({
            'code': 'T1081-XM', 'name': 'Xi măng thử 1081',
            'uom_id': unit.id, 'resource_type': 'material'})
        cls.sand = Res.create({
            'code': 'T1081-CAT', 'name': 'Cát thử 1081',
            'uom_id': unit.id, 'resource_type': 'material'})

        cls.pub = env['rp.price.publication'].create({
            'doc_no': 'T1081/2026', 'doc_date': '2026-11-01'})
        env['rp.price.line'].create([
            {'publication_id': cls.pub.id, 'resource_id': cls.cement.id,
             'price': 110_000.0, 'vat_included': 'yes', 'vat_rate': 10.0},
            {'publication_id': cls.pub.id, 'resource_id': cls.sand.id,
             'price': 300_000.0, 'vat_included': 'no', 'vat_rate': 10.0},
        ])

        project = env['rp.bid.project'].create({'name': 'Dự án thử 1081'})
        package = env['rp.bid.package'].create({
            'name': 'Gói thử 1081', 'project_id': project.id})
        cls.bid = env['rp.bid'].create({
            'name': 'Hồ sơ thử 1081', 'project_id': project.id,
            'package_id': package.id})
        cls.struct = env['rp.bid.structure'].create({
            'bid_id': cls.bid.id, 'name': 'Hạng mục thử 1081'})
        m3 = env['rp.progress.uom'].create({
            'name': 'm³ thử 1081', 'code': 'T1081-M3'})
        cls.line = env['rp.bid.boq.line'].create({
            'bid_structure_id': cls.struct.id, 'description': 'Công tác thử',
            'uom_id': m3.id, 'quantity': 10.0})

    # ------------------------------------------------------------------
    # 1403
    # ------------------------------------------------------------------
    def test_1403_duplicate_publication_keeps_price_lines(self):
        copy = self.pub.copy()
        self.assertEqual(copy.doc_no, 'T1081/2026 (bản sao)')
        self.assertEqual(copy.doc_date, self.pub.doc_date)
        self.assertEqual(len(copy.line_ids), 2,
                         'Bản sao phải mang theo dòng giá, không ra rỗng.')
        self.assertEqual(
            sorted(copy.line_ids.mapped('price')), [110_000.0, 300_000.0])
        self.assertEqual(
            sorted(copy.line_ids.mapped('vat_included')), ['no', 'yes'])
        self.assertEqual(len(self.pub.line_ids), 2,
                         'Bản gốc không được mất dòng.')

    def test_1403_copy_of_superseded_publication_is_not_superseded(self):
        newer = self.env['rp.price.publication'].create({
            'doc_no': 'T1081/2027', 'doc_date': '2027-01-01'})
        self.pub.superseded_by_id = newer
        copy = self.pub.copy()
        self.assertFalse(copy.superseded_by_id)
        self.assertFalse(copy.is_superseded)

    def test_1403_explicit_doc_no_wins(self):
        copy = self.pub.copy({'doc_no': 'T1081/2026-B'})
        self.assertEqual(copy.doc_no, 'T1081/2026-B')

    # ------------------------------------------------------------------
    # 1396
    # ------------------------------------------------------------------
    def test_1396_used_items_hidden_from_picker(self):
        Price = self.env['rp.bid.price']
        p = Price.create({'bid_id': self.bid.id,
                          'resource_id': self.cement.id, 'price': 1.0})
        self.assertEqual(self.bid.price_resource_ids, self.cement)
        # Danh sách bảng giá đứng riêng: dòng mới thấy item của dòng khác,
        # dòng đang có không tự ẩn item của chính nó.
        new = Price.new({'bid_id': self.bid.id})
        # Bản ghi new() trả quan hệ dạng NewId bọc id thật — so theo _origin.
        self.assertEqual(new.other_resource_ids._origin, self.cement)
        self.assertFalse(p.other_resource_ids)

    # ------------------------------------------------------------------
    # 1101
    # ------------------------------------------------------------------
    def test_1101_open_buttons_open_full_page_form(self):
        for rec in (self.line, self.struct):
            act = rec.action_open_form()
            self.assertEqual(act['type'], 'ir.actions.act_window')
            self.assertEqual(act['res_model'], rec._name)
            self.assertEqual(act['res_id'], rec.id)
            self.assertEqual(act['target'], 'current')

    # ------------------------------------------------------------------
    # 1381 — vế nạp lại màn hình
    # ------------------------------------------------------------------
    def test_1381_notification_reloads_view(self):
        self.env['rp.bid.price'].create({
            'bid_id': self.bid.id, 'resource_id': self.sand.id,
            'price': 2.0})
        res = self.bid.action_apply_price_list()
        self.assertEqual(res['tag'], 'display_notification')
        self.assertEqual(res['params']['next'],
                         {'type': 'ir.actions.client', 'tag': 'soft_reload'})
