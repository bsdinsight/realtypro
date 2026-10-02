# -*- coding: utf-8 -*-
"""Đường găng ở tầng DỰ ÁN — xuyên qua ranh giới hợp đồng.

Dựng một dự án hai hợp đồng, nối việc của hợp đồng này vào việc của hợp
đồng kia, rồi kiểm: số của tầng hợp đồng và số của tầng dự án phải KHÁC
nhau, và mốc phải xong phải làm dư địa âm khi lịch không còn kịp.
"""
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'rp_schedule')
class TestProjectCpm(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.project = cls.env['re.project'].create({
            'name': 'Proj-CPM', 'code': 'CPM',
            'expected_handover_date': '2026-12-31'})
        cls.subzone = cls.env['re.subzone'].create({
            'name': 'SZ-CPM', 'project_id': cls.project.id, 'code': 'SZ'})
        cls.structure = cls.env['rp.structure'].create({
            'name': 'HM-CPM', 'project_id': cls.project.id,
            'subzone_id': cls.subzone.id,
            'structure_level': 'item', 'structure_type': 'tower'})
        cls.package = cls.env['rp.tender.package'].create({
            'name': 'GT-CPM', 'project_id': cls.project.id})
        cls.env['rp.tender.package.line'].create({
            'package_id': cls.package.id,
            'structure_id': cls.structure.id})
        cls.c1 = cls._contract('HD-CPM-1', 'NT-CPM-1')
        cls.c2 = cls._contract('HD-CPM-2', 'NT-CPM-2')
        # HĐ 1: hai việc nối tiếp. HĐ 2: một việc, bắt đầu sau việc cuối
        # của HĐ 1 — đúng kiểu điểm bàn giao giữa hai nhà thầu.
        cls.t1 = cls._task(cls.c1, '1', 'Việc 1', '2026-01-01', '2026-01-10')
        cls.t2 = cls._task(cls.c1, '2', 'Việc 2', '2026-01-11', '2026-01-20',
                           preds=cls.t1)
        cls.t3 = cls._task(cls.c2, '1', 'Việc 3', '2026-01-21', '2026-02-10',
                           preds=cls.t2)

    @classmethod
    def _contract(cls, name, partner):
        contractor = cls.env['res.partner'].create({
            'is_contractor': True, 'is_company': True,
            'name': partner, 'ref': partner})
        c = cls.env['rp.contract'].create({
            'name': name, 'tender_package_id': cls.package.id,
            'contractor_id': contractor.id,
            'contract_value_pretax': 1_000_000_000.0,
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

    def test_project_id_suy_tu_hop_dong(self):
        self.assertEqual(self.t3.rp_project_id, self.project)
        self.assertEqual(self.project.schedule_task_count, 3)
        self.assertEqual(self.project.schedule_contract_count, 2)

    def test_gang_trong_hop_dong_khac_gang_toan_du_an(self):
        """Việc duy nhất của HĐ 2 luôn găng trong HĐ của nó.

        Nhìn cả dự án thì chuỗi mới có nghĩa: việc 1 và việc 2 của HĐ 1
        cũng nằm trên đường găng, vì chúng chặn việc của HĐ 2.
        """
        self.env['project.task'].rp_compute_critical_path(self.c1.id)
        self.env['project.task'].rp_compute_critical_path(self.c2.id)
        self.assertTrue(self.t3.is_critical)
        # Trong phạm vi HĐ 1, việc 2 là việc cuối nên găng; việc 1 chặn
        # việc 2 nên cũng găng.
        self.assertTrue(self.t2.is_critical)
        self.assertFalse(self.t1.is_project_critical,
                         'chưa tính tầng dự án thì field tầng dự án còn trống')

        self.env['project.task'].rp_compute_project_critical_path(
            self.project.id)
        for t in (self.t1, self.t2, self.t3):
            self.assertTrue(t.is_project_critical, t.name)
            self.assertEqual(t.project_float, 0, t.name)

    def test_du_dia_am_khi_tre_moc_phai_xong(self):
        """Mốc phải xong sớm hơn ngày dự báo → cả chuỗi ra dư địa âm."""
        self.project.expected_handover_date = '2026-01-31'
        self.project.invalidate_recordset()
        self.assertEqual(str(self.project.schedule_deadline), '2026-01-31')
        res = self.env['project.task'].rp_compute_project_critical_path(
            self.project.id)
        # Chuỗi về đích 10/02, hạn 31/01 → trễ 10 ngày.
        self.assertEqual(res[self.t3.id]['tf'], -10)
        self.assertTrue(res[self.t3.id]['critical'])
        self.assertEqual(self.project.schedule_deadline_slip, 10)

    def test_moc_phai_xong_muon_hon_khong_lam_mat_duong_gang(self):
        """Hạn còn xa thì vẫn phải có đường găng để nhìn.

        Nếu lấy hạn làm đích vô điều kiện thì mọi việc đều còn dư địa và
        màn hình không còn chuỗi nào được tô — nên hạn chỉ siết, không nới.
        """
        self.project.expected_handover_date = '2026-06-30'
        res = self.env['project.task'].rp_compute_project_critical_path(
            self.project.id)
        self.assertEqual(res[self.t3.id]['tf'], 0)
        self.assertTrue(res[self.t3.id]['critical'])

    def test_dong_tong_wbs_xet_theo_tung_hop_dong(self):
        """Hai hợp đồng trùng mã WBS không được coi nhau là dòng tổng."""
        child = self._task(self.c1, '1.1', 'Việc con của 1',
                           '2026-01-01', '2026-01-05')
        res = self.env['project.task'].rp_compute_project_critical_path(
            self.project.id)
        # '1' của HĐ 1 giờ là dòng tổng (có con '1.1') → ra khỏi phép tính.
        self.assertNotIn(self.t1.id, res)
        self.assertIn(child.id, res)
        # '1' của HĐ 2 KHÔNG có con, phải còn trong phép tính.
        self.assertIn(self.t3.id, res)

    def test_moc_su_kien_cho_gantt(self):
        marks = self.project._rp_schedule_markers()
        kinds = [m['kind'] for m in marks]
        self.assertIn('deadline', kinds)
        self.assertIn('today', kinds)
        self.assertEqual(
            [m['date'] for m in marks if m['kind'] == 'deadline'],
            ['2026-12-31'])
