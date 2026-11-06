# -*- coding: utf-8 -*-
"""Task 1081 — sáu điểm đã chốt với anh Đại ngày 06/11/2026.

1381  đổi định mức: bỏ đúng chi phí SINH TỪ định mức cũ; dòng sửa tay giữ
      và tô đỏ; dòng không rõ nguồn (nhập từ file) không bao giờ tự xoá
1382  đổi tên công việc / ĐVT theo định mức chỉ khi chưa sửa tay
1383  BoQ nhà thầu dùng chung bảng ĐVT uom.uom, quy đổi theo tên chuẩn hoá
1388  chặn trùng dòng công bố theo (công bố, tài nguyên, vùng, nguồn cung)
1404  danh mục LOẠI cấu kiện, tạo cấu kiện cho hồ sơ theo số lượng
1411  tổng hợp vật tư = khối lượng × định mức, cộng theo tài nguyên
"""
from psycopg2 import IntegrityError

from odoo.exceptions import UserError
from odoo.tests import Form, TransactionCase, tagged
from odoo.tools import mute_logger

from odoo.addons.rp_bid.models.rp_bid_uom import (
    norm_uom_name, progress_uom_from, resolve_uom, same_unit,
    uom_from_progress)


@tagged('post_install', '-at_install', 'rp_bid')
class TestTask1081Decisions(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        unit = env.ref('uom.product_uom_unit')
        Res = env['rp.resource']

        def res(code, typ):
            return Res.create({'code': code, 'name': 'Thử %s' % code,
                               'uom_id': unit.id, 'resource_type': typ})
        cls.xm = res('T81D-XM', 'material')
        cls.cat = res('T81D-CAT', 'material')
        cls.nc = res('T81D-NC', 'labor')
        cls.md = res('T81D-MD', 'machine')

        cls.m3 = env['uom.uom'].create({'name': 'm³ thử 81D'})
        cls.m2 = env['uom.uom'].create({'name': 'm² thử 81D'})
        nset = env['rp.norm.set'].create({'code': 'T81D', 'name': 'Bộ thử 81D'})
        N = env['rp.norm']
        cls.norm_a = N.create({'set_id': nset.id, 'code': 'T81D.KHOAN',
                               'name': 'Khoan tạo lỗ thử', 'uom_id': cls.m3.id})
        cls.norm_b = N.create({'set_id': nset.id, 'code': 'T81D.DAO',
                               'name': 'Đào đất thử', 'uom_id': cls.m3.id})
        cls.norm_c = N.create({'set_id': nset.id, 'code': 'T81D.TRAT',
                               'name': 'Trát tường thử', 'uom_id': cls.m2.id})
        env['rp.norm.line'].create([
            {'norm_id': cls.norm_a.id, 'resource_id': cls.xm.id, 'quantity': 1.0},
            {'norm_id': cls.norm_a.id, 'resource_id': cls.nc.id, 'quantity': 2.0},
            {'norm_id': cls.norm_b.id, 'resource_id': cls.md.id, 'quantity': 0.5},
            {'norm_id': cls.norm_b.id, 'resource_id': cls.nc.id, 'quantity': 1.0},
        ])
        cls.pub = env['rp.price.publication'].create({
            'doc_no': 'T81D/2026', 'doc_date': '2026-11-06'})
        env['rp.price.line'].create([
            {'publication_id': cls.pub.id, 'resource_id': r.id,
             'price': p, 'vat_included': 'no', 'vat_rate': 10.0}
            for r, p in ((cls.xm, 100.0), (cls.nc, 50.0), (cls.md, 1000.0))])

        project = env['rp.bid.project'].create({'name': 'Dự án thử 81D'})
        package = env['rp.bid.package'].create({
            'name': 'Gói thử 81D', 'project_id': project.id})
        cls.bid = env['rp.bid'].create({
            'name': 'Hồ sơ thử 81D', 'project_id': project.id,
            'package_id': package.id, 'norm_set_id': nset.id,
            'price_publication_id': cls.pub.id, 'element_prefix': 'CTN'})
        cls.struct = env['rp.bid.structure'].create({
            'bid_id': cls.bid.id, 'name': 'Hạng mục thử 81D'})

    def _line(self, norm=None, qty=10.0, **kw):
        vals = {'bid_structure_id': self.struct.id,
                'description': norm.name if norm else 'Công tác thử',
                'uom_id': self.m3.id, 'quantity': qty,
                'norm_id': norm.id if norm else False}
        vals.update(kw)
        return self.env['rp.bid.boq.line'].create(vals)

    # ------------------------------------------------------------------
    # 1381
    # ------------------------------------------------------------------
    def test_1381_change_norm_drops_only_old_norm_costs(self):
        line = self._line(self.norm_a)
        line.action_pull_norm()
        self.assertEqual(line.resource_line_ids.source_norm_id, self.norm_a)
        # Chi phí nhập từ file dự toán: không có nguồn định mức.
        imported = self.env['rp.bid.resource.line'].create({
            'line_id': line.id, 'resource_id': self.cat.id,
            'norm_qty': 3.0, 'unit_price': 10.0})

        line.norm_id = self.norm_b
        self.assertFalse(line.norm_pulled,
                         'Còn chi phí của định mức cũ thì nút phải còn hiện.')
        res = line.action_pull_norm()

        generated = line.resource_line_ids.filtered('source_norm_id')
        self.assertEqual(generated.source_norm_id, self.norm_b)
        self.assertEqual(set(generated.resource_id.ids),
                         {self.md.id, self.nc.id})
        self.assertEqual(
            generated.filtered(lambda l: l.resource_id == self.nc).norm_qty,
            1.0, 'Nhân công phải theo hao phí của định mức MỚI.')
        self.assertIn(imported, line.resource_line_ids,
                      'Dòng nhập từ file không bao giờ bị tự xoá.')
        self.assertIn('Bỏ 2 dòng chi phí của định mức cũ',
                      res['params']['message'])

    def test_1381_edited_old_norm_line_kept_and_flagged(self):
        line = self._line(self.norm_a)
        line.action_pull_norm()
        xm_line = line.resource_line_ids.filtered(
            lambda l: l.resource_id == self.xm)
        xm_line.norm_qty = 1.2           # người làm giá sửa tay
        self.assertTrue(xm_line.manual_edit)

        line.norm_id = self.norm_b
        res = line.action_pull_norm()
        self.assertTrue(xm_line.exists())
        self.assertTrue(xm_line.norm_stale)
        self.assertIn('GIỮ 1 dòng', res['params']['message'])
        self.assertTrue(line.norm_pulled,
                        'Dòng sửa tay không giữ nút ở trạng thái chưa xong.')

    def test_1381_price_list_apply_is_not_a_manual_edit(self):
        line = self._line(self.norm_a)
        line.action_pull_norm()
        self.env['rp.bid.price'].create({
            'bid_id': self.bid.id, 'resource_id': self.xm.id, 'price': 90.0})
        self.bid.action_apply_price_list()
        xm_line = line.resource_line_ids.filtered(
            lambda l: l.resource_id == self.xm)
        self.assertEqual(xm_line.unit_price, 90.0)
        self.assertFalse(xm_line.manual_edit)

    def test_1381_same_norm_again_only_adds_missing(self):
        line = self._line(self.norm_a)
        line.action_pull_norm()
        nc_line = line.resource_line_ids.filtered(
            lambda l: l.resource_id == self.nc)
        nc_line.norm_qty = 2.5
        line.resource_line_ids.filtered(
            lambda l: l.resource_id == self.xm).unlink()
        line.action_pull_norm()
        self.assertEqual(len(line.resource_line_ids), 2)
        self.assertEqual(nc_line.norm_qty, 2.5, 'Không ghi đè dòng đang có.')

    # ------------------------------------------------------------------
    # 1382
    # ------------------------------------------------------------------
    def test_1382_name_and_uom_follow_norm_until_edited(self):
        line = self._line(self.norm_a)
        with Form(line) as f:
            f.norm_id = self.norm_c
            self.assertEqual(f.description, self.norm_c.name)
            self.assertEqual(f.uom_id, self.m2)
            self.assertEqual(f.norm_code, 'T81D.TRAT')

    def test_1382_edited_name_and_uom_are_kept(self):
        line = self._line(self.norm_a, description='Khoan cọc theo HSMT',
                          uom_id=self.m2.id)
        with Form(line) as f:
            f.norm_id = self.norm_b
            self.assertEqual(f.description, 'Khoan cọc theo HSMT')
            self.assertEqual(f.uom_id, self.m2)
        self.assertTrue(line.uom_mismatch,
                        'm² so với định mức tính theo m³ phải bị đánh dấu.')

    # ------------------------------------------------------------------
    # 1383
    # ------------------------------------------------------------------
    def test_1383_unit_names_normalised(self):
        self.assertEqual(norm_uom_name('1m³'), 'm³')
        self.assertEqual(norm_uom_name(' M3 '), 'm³')
        self.assertEqual(norm_uom_name('Mét khối'), 'm³')
        self.assertEqual(norm_uom_name('100m³'), '100m³')
        self.assertEqual(norm_uom_name('md'), 'm')
        self.assertEqual(norm_uom_name('1md khoan'), 'md khoan')

    def test_1383_resolve_and_compare_units(self):
        env = self.env
        cube = resolve_uom(env, 'Mét khối')
        self.assertTrue(cube.active)
        self.assertEqual(resolve_uom(env, '1m³'), cube)
        self.assertEqual(resolve_uom(env, 'm3'), cube)
        hundred = resolve_uom(env, '100m³')
        self.assertEqual(hundred.relative_uom_id, cube)
        self.assertEqual(hundred.relative_factor, 100.0)
        self.assertFalse(same_unit(hundred, cube))
        drill = resolve_uom(env, '1md khoan')
        self.assertTrue(same_unit(drill, resolve_uom(env, 'm')))
        self.assertFalse(same_unit(cube, resolve_uom(env, 'tấn')))

    def test_1383_progress_unit_maps_both_ways(self):
        env = self.env
        pu = env['rp.progress.uom'].create({'name': 'Mét khối',
                                            'code': 'T81D-M3'})
        cube = uom_from_progress(env, pu)
        self.assertEqual(norm_uom_name(cube.name), 'm³')
        back = progress_uom_from(env, cube)
        self.assertIn('m³', {norm_uom_name(back.name),
                             norm_uom_name(back.code)})
        odd = progress_uom_from(env, env['uom.uom'].create(
            {'name': 'mặt cắt thử/lần'}))
        self.assertEqual(odd.name, 'mặt cắt thử/lần')

    # ------------------------------------------------------------------
    # 1388
    # ------------------------------------------------------------------
    def test_1388_duplicate_price_line_blocked_with_empty_region(self):
        Line = self.env['rp.price.line']
        vals = {'publication_id': self.pub.id, 'resource_id': self.cat.id,
                'price': 1.0, 'vat_included': 'no'}
        Line.create(vals)
        self.env.flush_all()
        with self.assertRaises(IntegrityError), \
                mute_logger('odoo.sql_db'), self.env.cr.savepoint():
            Line.create(dict(vals, price=2.0))
            self.env.flush_all()
        # Cùng tài nguyên nhưng khác vùng là hợp lệ — nhân công, ca máy.
        region = self.env['rp.price.region'].create({'name': 'Vùng thử 81D'})
        Line.create(dict(vals, price=3.0, region_id=region.id))
        self.env.flush_all()

    # ------------------------------------------------------------------
    # 1404
    # ------------------------------------------------------------------
    def test_1404_generate_elements_from_types(self):
        Type = self.env['rp.bid.element.type']
        Gen = self.env['rp.bid.element.generate']
        pile = Type.create({'code': 'T81D-CKN', 'name': 'Cọc D1200 thử',
                            'category': 'pile'})
        Gen.create({'bid_id': self.bid.id, 'line_ids': [
            (0, 0, {'type_id': pile.id, 'quantity': 3})]}).action_generate()
        els = self.bid.element_ids.filtered(lambda e: e.type_id == pile)
        self.assertEqual(len(els), 3)
        self.assertEqual(sorted(els.mapped('code')),
                         ['CTN-01', 'CTN-02', 'CTN-03'])
        self.assertEqual(sorted(els.mapped('name')),
                         ['Cọc D1200 thử số %s' % i for i in (1, 2, 3)])
        # Bấm thêm lần nữa: số thứ tự đi tiếp, không trùng tên.
        Gen.create({'bid_id': self.bid.id, 'line_ids': [
            (0, 0, {'type_id': pile.id, 'quantity': 2})]}).action_generate()
        els = self.bid.element_ids.filtered(lambda e: e.type_id == pile)
        self.assertIn('Cọc D1200 thử số 5', els.mapped('name'))
        self.assertIn('CTN-05', els.mapped('code'))
        with self.assertRaises(UserError):
            Gen.create({'bid_id': self.bid.id, 'line_ids': [
                (0, 0, {'type_id': pile.id, 'quantity': 0})]}
            ).action_generate()

    def test_1404_wizard_prefills_every_type(self):
        self.env['rp.bid.element.type'].create(
            {'code': 'T81D-PNL', 'name': 'Panel thử', 'category': 'wall'})
        wiz = self.env['rp.bid.element.generate'].with_context(
            default_bid_id=self.bid.id).new({})
        defaults = wiz.default_get(['line_ids'])
        self.assertTrue(defaults['line_ids'])

    # ------------------------------------------------------------------
    # 1411
    # ------------------------------------------------------------------
    def test_1411_material_summary(self):
        l1 = self._line(self.norm_a, qty=10.0)
        l2 = self._line(self.norm_a, qty=5.0)
        l3 = self._line(self.norm_a, qty=4.0, supplied_by='client')
        (l1 | l2 | l3).action_pull_norm()
        xm1 = l1.resource_line_ids.filtered(lambda l: l.resource_id == self.xm)
        self.assertEqual(xm1.resource_qty, 10.0)
        self.env.flush_all()
        rows = self.env['rp.bid.material.summary'].search(
            [('bid_id', '=', self.bid.id)])
        by = {(r.resource_id, r.supplied_by): r for r in rows}
        self.assertEqual(by[(self.xm, 'contractor')].quantity, 15.0)
        self.assertEqual(by[(self.nc, 'contractor')].quantity, 30.0)
        self.assertEqual(by[(self.xm, 'contractor')].line_count, 2)
        self.assertEqual(by[(self.xm, 'client')].quantity, 4.0,
                         'Vật tư bên mời cấp vẫn hiện, tách dòng riêng.')
        self.assertEqual(self.bid.material_summary_ids, rows)
