# -*- coding: utf-8 -*-
"""Khiếu nại, gia hạn và phạt chậm — ba thứ phải khớp với nhau."""
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'rp_claim')
class TestClaim(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.project = cls.env['re.project'].create({
            'name': 'Proj-CL', 'code': 'CL'})
        cls.subzone = cls.env['re.subzone'].create({
            'name': 'SZ-CL', 'project_id': cls.project.id, 'code': 'SZ'})
        cls.structure = cls.env['rp.structure'].create({
            'name': 'HM-CL', 'project_id': cls.project.id,
            'subzone_id': cls.subzone.id,
            'structure_level': 'item', 'structure_type': 'tower'})
        cls.package = cls.env['rp.tender.package'].create({
            'name': 'GT-CL', 'project_id': cls.project.id})
        cls.env['rp.tender.package.line'].create({
            'package_id': cls.package.id, 'structure_id': cls.structure.id})
        partner = cls.env['res.partner'].create({
            'is_contractor': True, 'is_company': True,
            'name': 'NT-CL', 'ref': 'NT-CL'})
        cls.contract = cls.env['rp.contract'].create({
            'name': 'HD-CL', 'tender_package_id': cls.package.id,
            'contractor_id': partner.id,
            'contract_value_pretax': 1_000_000_000.0,
            'date_start': '2026-01-01', 'date_end': '2026-06-30'})
        cls.contract.action_sign()
        # Lịch của hợp đồng về đích 30/07 → chậm 30 ngày so mốc 30/06.
        cls.task = cls.env['project.task'].create({
            'name': 'Việc cuối',
            'project_id': cls.contract._get_or_create_schedule_project().id,
            'rp_contract_id': cls.contract.id, 'wbs_code': '1',
            'planned_start': '2026-01-01', 'planned_end': '2026-07-30'})

    def _claim(self, **kw):
        vals = {
            'name': 'Xin gia hạn do chậm bàn giao mặt bằng',
            'contract_id': self.contract.id,
            'claim_type': 'eot',
            'date_event': '2026-03-01',
            'notice_days': 28,
            'eot_days_claimed': 30,
        }
        vals.update(kw)
        return self.env['rp.claim'].create(vals)

    # --- hạn thông báo ---------------------------------------------
    def test_han_thong_bao_dung_han(self):
        c = self._claim(date_notice='2026-03-20')
        self.assertEqual(str(c.notice_deadline), '2026-03-29')
        self.assertTrue(c.notice_ok)
        self.assertEqual(c.notice_late_days, 0)

    def test_han_thong_bao_qua_han(self):
        c = self._claim(date_notice='2026-04-10')
        self.assertFalse(c.notice_ok)
        self.assertEqual(c.notice_late_days, 12)

    def test_ma_tu_sinh(self):
        c = self._claim()
        self.assertTrue(c.code and c.code != '/')

    # --- quy trình và gia hạn ---------------------------------------
    def test_chap_thuan_mot_phan(self):
        c = self._claim(date_notice='2026-03-10')
        c.action_notify()
        c.action_submit()
        c.eot_days_granted = 20
        c.action_agree()
        self.assertEqual(c.state, 'partial')
        self.assertTrue(c.decision_date)

    def test_chap_thuan_toan_bo_lay_dung_so_xin(self):
        c = self._claim(date_notice='2026-03-10')
        c.action_notify()
        c.action_submit()
        c.action_agree()
        self.assertEqual(c.state, 'agreed')
        self.assertEqual(c.eot_days_granted, 30)

    def test_gia_han_doi_moc_hop_dong(self):
        """Gia hạn được chấp thuận phải dời mốc tính phạt."""
        self.assertEqual(str(self.contract.date_completion_adjusted),
                         '2026-06-30')
        c = self._claim(date_notice='2026-03-10')
        c.action_notify()
        c.action_submit()
        c.action_agree()
        self.contract.invalidate_recordset()
        self.assertEqual(self.contract.eot_days_granted, 30)
        self.assertEqual(str(self.contract.date_completion_adjusted),
                         '2026-07-30')

    def test_phu_luc_gia_han(self):
        c = self._claim(date_notice='2026-03-10')
        c.action_notify()
        c.action_submit()
        c.action_agree()
        c.action_create_amendment()
        self.assertTrue(c.amendment_id)
        self.assertEqual(c.amendment_id.amendment_type, 'extension')
        self.assertEqual(str(c.amendment_id.new_date_end), '2026-07-30')
        with self.assertRaises(UserError):
            c.action_create_amendment()

    def test_tu_choi_thi_khong_gia_han(self):
        c = self._claim(date_notice='2026-03-10')
        c.action_notify()
        c.action_submit()
        c.action_reject()
        self.assertEqual(c.eot_days_granted, 0)
        self.contract.invalidate_recordset()
        self.assertEqual(self.contract.eot_days_granted, 0)
        with self.assertRaises(UserError):
            c.action_create_amendment()

    # --- phạt chậm ---------------------------------------------------
    def test_phat_cham_theo_moc_chua_gia_han(self):
        self.contract.invalidate_recordset()
        self.assertEqual(str(self.contract.ld_forecast_end), '2026-07-30')
        self.assertEqual(self.contract.ld_days_late, 30)
        # 1 tỷ × 0,05%/ngày × 30 ngày = 15 triệu
        self.assertAlmostEqual(self.contract.ld_amount_exposure,
                               15_000_000.0, places=0)
        self.assertFalse(self.contract.ld_capped)

    def test_gia_han_lam_giam_tien_phat(self):
        c = self._claim(date_notice='2026-03-10', eot_days_claimed=20)
        c.action_notify()
        c.action_submit()
        c.action_agree()
        self.contract.invalidate_recordset()
        self.assertEqual(self.contract.ld_days_late, 10)
        self.assertAlmostEqual(self.contract.ld_amount_exposure,
                               5_000_000.0, places=0)

    def test_tran_phat(self):
        """Chậm rất lâu thì tiền phạt dừng ở trần hợp đồng."""
        self.task.planned_end = '2028-06-30'
        self.contract.invalidate_recordset()
        self.assertTrue(self.contract.ld_capped)
        self.assertAlmostEqual(
            self.contract.ld_amount_exposure,
            self.contract.contract_value_pretax
            * self.contract.ld_cap_percent / 100.0, places=0)

    def test_bien_ban_dong_bang_so_lieu(self):
        res = self.contract.action_create_ld_assessment()
        a = self.env['rp.ld.assessment'].browse(res['res_id'])
        self.assertEqual(a.days_late, 30)
        self.assertAlmostEqual(a.amount, 15_000_000.0, places=0)
        # Lịch đổi sau khi lập: biên bản KHÔNG được chạy theo
        self.task.planned_end = '2026-09-30'
        self.contract.invalidate_recordset()
        a.invalidate_recordset()
        self.assertEqual(self.contract.ld_days_late, 92)
        self.assertEqual(a.days_late, 30)
        # Đã thông báo thì không chụp lại được nữa
        a.action_notify()
        with self.assertRaises(UserError):
            a.action_refresh()
