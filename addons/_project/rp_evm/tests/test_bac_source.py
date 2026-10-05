# -*- coding: utf-8 -*-
"""BAC lấy ở cấp nào — và tuyệt đối không đếm đúp.

Ngân sách phải đặt ở cấp mà chủ đầu tư KÝ được hợp đồng và ĐO được tiền
ra. Mua trọn gói EPC thì cấp đó là GÓI THẦU (BOQ của chủ đầu tư); tự làm
và đo khối lượng thì là HẠNG MỤC. Hệ thống đỡ cả hai, nhưng hạng mục đã
nằm trong một gói CÓ ngân sách thì không được cộng lần thứ hai.
"""
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'rp_evm')
class TestBacSource(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.project = cls.env['re.project'].create({
            'name': 'Proj-BAC', 'code': 'BACX',
            'expected_handover_date': '2027-12-31'})
        cls.subzone = cls.env['re.subzone'].create({
            'name': 'SZ-BAC', 'project_id': cls.project.id, 'code': 'SZ'})
        cls.structure = cls.env['rp.structure'].create({
            'name': 'HM-BAC', 'project_id': cls.project.id,
            'subzone_id': cls.subzone.id,
            'structure_level': 'item', 'structure_type': 'tower'})
        cls.package = cls.env['rp.tender.package'].create({
            'name': 'GT-BAC', 'project_id': cls.project.id})
        cls.env['rp.tender.package.line'].create({
            'package_id': cls.package.id,
            'structure_id': cls.structure.id})
        cls.uom = cls.env['rp.progress.uom'].search([], limit=1)
        cls.cat = cls.env['rp.cost.category'].search(
            [('project_id', '=', cls.project.id)], limit=1)
        cls.Boq = cls.env['rp.boq.line']

    def _boq(self, **kw):
        vals = {'description': 'Đầu mục', 'category_id': self.cat.id,
                'uom_id': self.uom.id, 'quantity': 1, 'unit_price': 0.0}
        vals.update(kw)
        return self.Boq.create(vals)

    def test_chua_khai_goi_thi_lay_theo_hang_muc(self):
        self._boq(structure_id=self.structure.id, unit_price=1_000.0)
        self.project.invalidate_recordset()
        self.assertEqual(self.project.total_bac, 1_000.0)

    def test_khai_ngan_sach_goi_thi_khong_cong_hang_muc_nua(self):
        """Hạng mục thuộc gói đã có ngân sách → KHÔNG cộng lần hai."""
        self._boq(structure_id=self.structure.id, unit_price=1_000.0)
        self._boq(package_id=self.package.id, unit_price=900.0)
        self.package.invalidate_recordset()
        self.project.invalidate_recordset()
        self.assertEqual(self.package.budget_amount, 900.0)
        self.assertEqual(self.project.total_bac, 900.0,
                         'Lấy ngân sách gói, bỏ dự toán hạng mục trong gói')

    def test_dong_khong_co_gia_khong_cong_tien(self):
        self._boq(package_id=self.package.id, unit_price=500.0)
        self._boq(package_id=self.package.id, unit_price=300.0,
                  line_status='included')
        self._boq(package_id=self.package.id, unit_price=200.0,
                  line_status='excluded')
        self.package.invalidate_recordset()
        self.assertEqual(self.package.budget_amount, 500.0)

    def test_chi_phuong_an_duoc_chon_moi_vao_ngan_sach(self):
        self._boq(package_id=self.package.id, unit_price=100.0,
                  option_code='PA1', is_selected=True)
        self._boq(package_id=self.package.id, unit_price=130.0,
                  option_code='PA2', is_selected=False)
        self.package.invalidate_recordset()
        self.assertEqual(self.package.budget_amount, 100.0)
        self.assertEqual(self.package.budget_vs_contract, -100.0,
                         'Chưa có hợp đồng thì chênh = âm ngân sách')

    def test_hai_cot_tien_cong_lai(self):
        ln = self._boq(package_id=self.package.id, quantity=0,
                       unit_price=0.0, amount_supply=700.0,
                       amount_install=300.0)
        self.assertEqual(ln.amount, 1_000.0)

    def test_phai_gan_vao_hang_muc_hoac_goi(self):
        from odoo.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            self._boq(unit_price=100.0)
