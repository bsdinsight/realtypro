# -*- coding: utf-8 -*-
"""Sổ ranh giới: ràng buộc hai bên, đối chiếu lịch, và quét từ lịch."""
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'rp_interface')
class TestInterface(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.project = cls.env['re.project'].create({
            'name': 'Proj-IF', 'code': 'IF'})
        cls.subzone = cls.env['re.subzone'].create({
            'name': 'SZ-IF', 'project_id': cls.project.id, 'code': 'SZ'})
        cls.structure = cls.env['rp.structure'].create({
            'name': 'HM-IF', 'project_id': cls.project.id,
            'subzone_id': cls.subzone.id,
            'structure_level': 'item', 'structure_type': 'tower'})
        cls.package = cls.env['rp.tender.package'].create({
            'name': 'GT-IF', 'project_id': cls.project.id})
        cls.env['rp.tender.package.line'].create({
            'package_id': cls.package.id, 'structure_id': cls.structure.id})
        cls.c_giao = cls._contract('HD-IF-GIAO', 'NT-IF-GIAO')
        cls.c_nhan = cls._contract('HD-IF-NHAN', 'NT-IF-NHAN')
        # Bên giao xong 20/01, bên nhận khởi công 21/01 → vừa khít.
        cls.t_giao = cls._task(cls.c_giao, '1', 'Đổ bê tông móng',
                               '2026-01-01', '2026-01-20')
        cls.t_nhan = cls._task(cls.c_nhan, '1', 'Lắp dựng tháp',
                               '2026-01-21', '2026-02-10')

    @classmethod
    def _contract(cls, name, partner):
        p = cls.env['res.partner'].create({
            'is_contractor': True, 'is_company': True,
            'name': partner, 'ref': partner})
        c = cls.env['rp.contract'].create({
            'name': name, 'tender_package_id': cls.package.id,
            'contractor_id': p.id, 'contract_value_pretax': 1e9,
            'date_end': '2026-12-31'})
        c.action_sign()
        return c

    @classmethod
    def _task(cls, contract, wbs, name, start, end, preds=None):
        return cls.env['project.task'].create({
            'name': name,
            'project_id': contract._get_or_create_schedule_project().id,
            'rp_contract_id': contract.id, 'wbs_code': wbs,
            'planned_start': start, 'planned_end': end,
            'predecessor_ids': [(6, 0, preds.ids)] if preds else False,
        })

    def _interface(self, **kw):
        vals = {
            'name': 'Bàn giao móng cho bên lắp dựng',
            'project_id': self.project.id,
            'from_contract_id': self.c_giao.id,
            'to_contract_id': self.c_nhan.id,
            'from_task_id': self.t_giao.id,
            'to_task_id': self.t_nhan.id,
        }
        vals.update(kw)
        return self.env['rp.interface'].create(vals)

    def test_ma_tu_sinh(self):
        i = self._interface()
        self.assertTrue(i.code and i.code != '/')
        self.assertIn(i.code, i.display_name)

    def test_hai_ben_phai_khac_nhau(self):
        with self.assertRaises(UserError):
            self._interface(to_contract_id=self.c_giao.id,
                            to_task_id=False)

    def test_viec_phai_thuoc_dung_hop_dong(self):
        with self.assertRaises(UserError):
            self._interface(from_task_id=self.t_nhan.id)

    def test_du_dia_lay_tu_lich(self):
        i = self._interface()
        self.assertEqual(str(i.schedule_ready_date), '2026-01-20')
        self.assertEqual(str(i.schedule_need_date), '2026-01-21')
        self.assertEqual(i.gap_days, 1)
        self.assertFalse(i.is_conflict)

    def test_lich_mau_thuan_khi_ben_nhan_can_truoc(self):
        """Bên giao lùi 10 ngày → bên nhận phải chờ, dư địa âm."""
        i = self._interface()
        self.t_giao.planned_end = '2026-01-31'
        i.invalidate_recordset()
        self.assertEqual(i.gap_days, -10)
        self.assertTrue(i.is_conflict)

    def test_noi_vao_lich(self):
        i = self._interface()
        self.assertFalse(i.linked_in_schedule)
        i.action_link_schedule()
        self.assertIn(self.t_giao, self.t_nhan.predecessor_ids)
        self.assertTrue(i.linked_in_schedule)
        # Gọi lại không nhân đôi quan hệ
        i.action_link_schedule()
        self.assertEqual(len(self.t_nhan.predecessor_ids), 1)

    def test_noi_vao_lich_thieu_viec_thi_bao_loi(self):
        i = self._interface(from_task_id=False)
        with self.assertRaises(UserError):
            i.action_link_schedule()

    def test_quet_tu_lich(self):
        """Quét chỉ bắt quan hệ NỐI HAI HỢP ĐỒNG, và chạy lại được."""
        # cùng hợp đồng → không phải điểm bàn giao
        self._task(self.c_giao, '2', 'Bảo dưỡng móng',
                   '2026-01-21', '2026-01-25', preds=self.t_giao)
        # khác hợp đồng → là điểm bàn giao
        self.t_nhan.predecessor_ids = [(6, 0, self.t_giao.ids)]
        self.project.action_scan_interfaces()
        ifs = self.env['rp.interface'].search(
            [('project_id', '=', self.project.id)])
        self.assertEqual(len(ifs), 1)
        self.assertEqual(ifs.from_task_id, self.t_giao)
        self.assertEqual(ifs.to_task_id, self.t_nhan)
        self.project.action_scan_interfaces()
        self.assertEqual(self.env['rp.interface'].search_count(
            [('project_id', '=', self.project.id)]), 1,
            'quét lại không được tạo trùng')

    def test_thong_ke_du_an_va_hop_dong(self):
        i = self._interface()
        self.project.invalidate_recordset()
        self.assertEqual(self.project.interface_count, 1)
        self.assertEqual(self.project.interface_open_count, 1)
        self.assertEqual(self.c_giao.interface_out_count, 1)
        self.assertEqual(self.c_nhan.interface_in_count, 1)
        i.action_deliver()
        self.assertEqual(str(i.state), 'delivered')
        self.assertTrue(i.date_actual)
        self.project.invalidate_recordset()
        self.assertEqual(self.project.interface_open_count, 0)
