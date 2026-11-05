# -*- coding: utf-8 -*-
"""Giá hai gốc VAT trong hồ sơ dự thầu — hai lỗi đã sửa.

Chi phí tính trên giá chưa VAT, VAT cộng đúng một lần ở giá dự thầu, và
bảng chào xuất đơn giá theo đúng gốc VAT mà mẫu biểu giá của HSMT yêu
cầu. Đây là kịch bản nghiệm thu 12 và 13 của Blueprint Dự thầu bản 2.

Số chọn cho dễ nhẩm: markup 0, thuế suất 10%, 10 m³ công tác, mỗi m³ ăn
1 đơn vị xi măng (công bố 110.000 ĐÃ GỒM VAT), 2 công (50.000 chưa VAT)
và 1 đơn vị phụ gia (20.000 KHÔNG RÕ VAT).

    chi phí / m³  = 100.000 + 2 × 50.000 + 20.000 = 220.000
    T = G         = 10 × 220.000                  = 2.200.000
    VAT 10%                                        =   220.000
    GIÁ DỰ THẦU                                    = 2.420.000

Lỗi cũ đưa nguyên 110.000 vào chi phí: T = 2.300.000, VAT bị tính trên
phần VAT đã nằm sẵn trong giá xi măng.
"""
import base64
import io

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'rp_bid')
class TestBidVat(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        unit = env.ref('uom.product_uom_unit')
        Res = env['rp.resource']
        cls.cement = Res.create({
            'code': 'TVAT-XM', 'name': 'Xi măng thử VAT', 'uom_id': unit.id,
            'resource_type': 'material'})
        cls.worker = Res.create({
            'code': 'TVAT-NC', 'name': 'Nhân công thử VAT',
            'uom_id': unit.id, 'resource_type': 'labor'})
        cls.additive = Res.create({
            'code': 'TVAT-PG', 'name': 'Phụ gia thử VAT', 'uom_id': unit.id,
            'resource_type': 'material'})

        nset = env['rp.norm.set'].create({
            'code': 'TVAT', 'name': 'Bộ định mức thử VAT'})
        cls.norm = env['rp.norm'].create({
            'set_id': nset.id, 'code': 'TVAT.001', 'name': 'Công tác thử'})
        env['rp.norm.line'].create([
            {'norm_id': cls.norm.id, 'resource_id': cls.cement.id,
             'quantity': 1.0},
            {'norm_id': cls.norm.id, 'resource_id': cls.worker.id,
             'quantity': 2.0},
            {'norm_id': cls.norm.id, 'resource_id': cls.additive.id,
             'quantity': 1.0},
        ])

        pub = env['rp.price.publication'].create({
            'doc_no': 'TVAT/2026', 'doc_date': '2026-11-01'})
        env['rp.price.line'].create([
            {'publication_id': pub.id, 'resource_id': cls.cement.id,
             'price': 110_000.0, 'vat_included': 'yes', 'vat_rate': 10.0},
            {'publication_id': pub.id, 'resource_id': cls.worker.id,
             'price': 50_000.0, 'vat_included': 'no', 'vat_rate': 10.0},
            {'publication_id': pub.id, 'resource_id': cls.additive.id,
             'price': 20_000.0, 'vat_included': 'unknown'},
        ])

        project = env['rp.bid.project'].create({'name': 'Dự án thử VAT'})
        package = env['rp.bid.package'].create({
            'name': 'Gói thử VAT', 'project_id': project.id})
        cls.bid = env['rp.bid'].create({
            'name': 'Hồ sơ thử VAT', 'project_id': project.id,
            'package_id': package.id, 'norm_set_id': nset.id,
            'price_publication_id': pub.id,
            'overhead_pct': 0.0, 'temp_facility_pct': 0.0,
            'undefined_work_pct': 0.0, 'profit_pct': 0.0,
            'vat_pct': 10.0, 'contingency_pct': 0.0})
        cls.item = env['rp.bid.item'].create({
            'bid_id': cls.bid.id, 'code': 'A.1', 'name': 'Công tác thử',
            'uom_text': 'm3', 'quantity_client': 10.0})
        struct = env['rp.bid.structure'].create({
            'bid_id': cls.bid.id, 'name': 'Hạng mục thử',
            'item_id': cls.item.id})
        m3 = env['rp.progress.uom'].create({'name': 'm³ thử', 'code': 'TVAT-M3'})
        cls.line = env['rp.bid.boq.line'].create({
            'bid_structure_id': struct.id, 'description': 'Công tác thử',
            'uom_id': m3.id, 'quantity': 10.0, 'norm_id': cls.norm.id})
        cls.pull_result = cls.line.action_pull_norm()

    # ------------------------------------------------------------------
    # Lỗi 2 — giá đầu vào
    # ------------------------------------------------------------------
    def _cost_line(self, resource):
        return self.line.resource_line_ids.filtered(
            lambda r: r.resource_id == resource)

    def test_published_price_with_vat_enters_cost_ex_vat(self):
        """Kịch bản 12: công bố "đã gồm VAT" vào chi phí ở giá chưa VAT."""
        self.assertAlmostEqual(self._cost_line(self.cement).unit_price,
                               100_000.0, places=2)
        self.assertAlmostEqual(self._cost_line(self.worker).unit_price,
                               50_000.0, places=2)

    def test_unknown_vat_kept_and_reported(self):
        """Không rõ VAT: giữ nguyên số, báo ra — không đoán."""
        self.assertAlmostEqual(self._cost_line(self.additive).unit_price,
                               20_000.0, places=2)
        msg = self.pull_result['params']['message']
        self.assertIn('1 dòng giá công bố ghi đã gồm VAT', msg)
        self.assertIn('1 dòng lấy giá công bố KHÔNG RÕ VAT', msg)

    def test_vat_added_exactly_once(self):
        bid = self.bid
        self.assertAlmostEqual(bid.direct_cost, 2_200_000.0, places=2)
        self.assertAlmostEqual(bid.pre_tax_total, 2_200_000.0, places=2)
        self.assertAlmostEqual(bid.vat_amount, 220_000.0, places=2)
        self.assertAlmostEqual(bid.bid_total, 2_420_000.0, places=2)
        self.assertAlmostEqual(
            bid.vat_amount, bid.pre_tax_total * bid.vat_pct / 100.0, places=2)

    def test_bid_price_library_compares_ex_vat(self):
        """Bảng giá gói so với thư viện CÙNG gốc chưa VAT."""
        Price = self.env['rp.bid.price']
        cement = Price.create({'bid_id': self.bid.id,
                               'resource_id': self.cement.id,
                               'price': 100_000.0})
        self.assertAlmostEqual(cement.library_price, 100_000.0, places=2)
        self.assertAlmostEqual(cement.variance, 0.0, places=2)
        self.assertFalse(cement.library_vat_unknown)

        additive = Price.create({'bid_id': self.bid.id,
                                 'resource_id': self.additive.id})
        self.assertTrue(additive.library_vat_unknown)
        res = additive.action_take_library_price()
        self.assertAlmostEqual(additive.price, 20_000.0, places=2)
        self.assertIn('KHÔNG RÕ VAT', additive.note)
        self.assertIn('KHÔNG RÕ VAT', res['params']['message'])

    # ------------------------------------------------------------------
    # Lỗi 1 — đơn giá chào
    # ------------------------------------------------------------------
    def test_offer_unit_price_follows_declared_basis(self):
        item = self.item
        self.assertAlmostEqual(item.amount_offer, 2_420_000.0, places=2)
        self.assertAlmostEqual(item.amount_offer_ex_vat, 2_200_000.0, places=2)
        self.assertAlmostEqual(item.unit_price_inc_vat, 242_000.0, places=2)
        self.assertAlmostEqual(item.unit_price_ex_vat, 220_000.0, places=2)

        # Chưa khai gốc → ô điền vào file để trống, không đoán.
        self.assertFalse(self.bid.offer_vat_basis)
        self.assertEqual(item.unit_price_offer, 0.0)

        self.bid.offer_vat_basis = 'excl'
        self.assertAlmostEqual(item.unit_price_offer, 220_000.0, places=2)
        self.bid.offer_vat_basis = 'incl'
        self.assertAlmostEqual(item.unit_price_offer, 242_000.0, places=2)

    def test_export_refuses_without_basis(self):
        self.assertFalse(self.bid.offer_vat_basis)
        with self.assertRaises(UserError):
            self.bid.action_export_offer()

    def _export_rows(self):
        from openpyxl import load_workbook
        self.bid.action_export_offer()
        wb = load_workbook(io.BytesIO(base64.b64decode(self.bid.export_file)))
        return [r for r in wb.active.iter_rows(values_only=True)]

    def _row(self, rows, label):
        hits = [r for r in rows if r[1] == label]
        self.assertEqual(len(hits), 1, label)
        return hits[0]

    def test_export_excl_adds_vat_once_at_total(self):
        """Kịch bản 13: đơn giá chưa VAT, VAT ở dòng tổng, tổng sau thuế
        khớp giá dự thầu — kể cả khi có dự phòng."""
        self.bid.write({'offer_vat_basis': 'excl', 'contingency_pct': 5.0})
        self.assertAlmostEqual(self.bid.bid_total, 2_541_000.0, places=2)
        rows = self._export_rows()
        line = [r for r in rows if r[0] == 'A.1'][0]
        self.assertEqual(line[4], 231_000)          # đơn giá chưa VAT
        self.assertEqual(line[5], 2_310_000)
        self.assertEqual(
            self._row(rows, 'Tổng cộng (chưa gồm thuế GTGT)')[5], 2_310_000)
        self.assertEqual(self._row(rows, 'Thuế GTGT 10%')[5], 231_000)
        self.assertEqual(
            self._row(rows, 'Tổng cộng (đã gồm thuế GTGT)')[5],
            round(self.bid.bid_total))
        notes = ' '.join(str(r[1]) for r in rows if r[1])
        self.assertIn('CHƯA bao gồm thuế GTGT', notes)
        self.assertIn('dự phòng', notes)

    def test_export_incl_has_no_separate_vat_line(self):
        self.bid.offer_vat_basis = 'incl'
        rows = self._export_rows()
        line = [r for r in rows if r[0] == 'A.1'][0]
        self.assertEqual(line[4], 242_000)
        self.assertEqual(line[5], 2_420_000)
        self.assertFalse([r for r in rows
                          if str(r[1] or '').startswith('Thuế GTGT')])
        self.assertEqual(
            self._row(rows, 'Tổng cộng (đã gồm thuế GTGT)')[5], 2_420_000)
