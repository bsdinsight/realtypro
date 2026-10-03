# -*- coding: utf-8 -*-
"""Sổ phát sinh: đồng hồ 14 ngày, vào giá hợp đồng, và dự báo ngân sách."""
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'rp_variation')
class TestVariation(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.project = cls.env['re.project'].create({
            'name': 'Proj-VR', 'code': 'VR'})
        cls.subzone = cls.env['re.subzone'].create({
            'name': 'SZ-VR', 'project_id': cls.project.id, 'code': 'SZ'})
        cls.structure = cls.env['rp.structure'].create({
            'name': 'HM-VR', 'project_id': cls.project.id,
            'subzone_id': cls.subzone.id,
            'structure_level': 'item', 'structure_type': 'tower'})
        cls.package = cls.env['rp.tender.package'].create({
            'name': 'GT-VR', 'project_id': cls.project.id})
        cls.env['rp.tender.package.line'].create({
            'package_id': cls.package.id, 'structure_id': cls.structure.id})
        partner = cls.env['res.partner'].create({
            'is_contractor': True, 'is_company': True,
            'name': 'NT-VR', 'ref': 'NT-VR'})
        cls.contract = cls.env['rp.contract'].create({
            'name': 'HD-VR', 'tender_package_id': cls.package.id,
            'contractor_id': partner.id,
            'contract_value_pretax': 1_000_000_000.0,
            'date_end': '2026-12-31'})
        cls.contract.action_sign()

    def _variation(self, **kw):
        vals = {
            'name': 'Bổ sung đường công vụ',
            'contract_id': self.contract.id,
            'origin': 'proposal_request',
            'date_event': '2026-03-01',
            'date_request': '2026-03-01',
        }
        vals.update(kw)
        return self.env['rp.variation'].create(vals)

    # --- đồng hồ điều 13 --------------------------------------------
    def test_han_bao_gia_14_ngay(self):
        v = self._variation()
        self.assertEqual(str(v.quote_due_date), '2026-03-15')
        v.date_quote = '2026-03-10'
        self.assertTrue(v.quote_on_time)
        self.assertEqual(v.quote_late_days, 0)

    def test_bao_gia_qua_han(self):
        v = self._variation(date_quote='2026-03-25')
        self.assertFalse(v.quote_on_time)
        self.assertEqual(v.quote_late_days, 10)

    def test_han_phan_doi_chi_thi(self):
        v = self._variation(date_instruction='2026-04-01')
        self.assertEqual(str(v.objection_due_date), '2026-04-15')

    # --- giá trị ------------------------------------------------------
    def test_cong_tien_tu_dong_khoi_luong(self):
        v = self._variation(line_ids=[
            (0, 0, {'name': 'Đào đắp', 'quantity': 1000,
                    'unit_price': 120_000}),
            (0, 0, {'name': 'Cống', 'quantity': 10, 'unit_price': 5_000_000}),
        ])
        self.assertEqual(v.amount_lines, 170_000_000)

    def test_duyet_lay_dung_gia_de_xuat(self):
        v = self._variation(amount_quoted=200_000_000)
        v.action_request_quote()
        v.action_receive_quote()
        v.action_approve()
        self.assertEqual(v.state, 'approved')
        self.assertEqual(v.amount_approved, 200_000_000)

    def test_vao_gia_hop_dong_qua_phu_luc(self):
        """Nút 'đưa vào giá hợp đồng' phải ĐỔI THẬT giá trị hợp đồng."""
        v = self._variation(amount_quoted=200_000_000)
        v.action_request_quote()
        v.action_receive_quote()
        v.action_approve()
        v.action_apply_to_contract()
        self.assertEqual(v.state, 'applied')
        self.assertTrue(v.amendment_id)
        self.assertEqual(v.amendment_id.amendment_type, 'value')
        self.assertEqual(v.amendment_id.state, 'applied')
        self.contract.invalidate_recordset()
        self.assertEqual(self.contract.contract_value_pretax,
                         1_200_000_000.0)
        with self.assertRaises(UserError):
            v.action_apply_to_contract()

    def test_chua_duyet_thi_chua_duoc_vao_hop_dong(self):
        v = self._variation(amount_quoted=200_000_000)
        with self.assertRaises(UserError):
            v.action_apply_to_contract()

    # --- dự báo ngân sách --------------------------------------------
    def test_du_bao_khong_dem_dup_phan_da_vao_hop_dong(self):
        """Phát sinh đã vào phụ lục thì giá HĐ đã gồm — không cộng hai lần."""
        v1 = self._variation(amount_quoted=200_000_000)
        v1.action_request_quote()
        v1.action_receive_quote()
        v1.action_approve()
        v1.action_apply_to_contract()
        v2 = self._variation(name='Phát sinh đang chờ',
                             amount_quoted=50_000_000)
        v2.action_request_quote()
        v2.action_receive_quote()
        self.contract.invalidate_recordset()
        self.assertEqual(self.contract.contract_value_pretax, 1_200_000_000)
        self.assertEqual(self.contract.variation_pending_amount, 50_000_000)
        self.assertEqual(self.contract.contract_value_forecast,
                         1_250_000_000)
        self.project.invalidate_recordset()
        self.assertEqual(self.project.contract_committed_total,
                         1_200_000_000)
        self.assertEqual(self.project.cost_forecast_total, 1_250_000_000)

    def test_phat_sinh_am_giam_du_bao(self):
        v = self._variation(name='Tối ưu thiết kế', amount_quoted=-30_000_000,
                            origin='value_engineering')
        v.action_request_quote()
        v.action_receive_quote()
        v.action_approve()
        self.project.invalidate_recordset()
        self.assertEqual(self.project.variation_approved_total, -30_000_000)
        self.assertEqual(self.project.cost_forecast_total, 970_000_000)

    def test_mo_khieu_nai_gia_han_tu_phat_sinh(self):
        v = self._variation(eot_days_claimed=21)
        v.action_create_eot_claim()
        self.assertTrue(v.claim_id)
        self.assertEqual(v.claim_id.claim_type, 'eot')
        self.assertEqual(v.claim_id.eot_days_claimed, 21)
        with self.assertRaises(UserError):
            v.action_create_eot_claim()
