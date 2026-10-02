# -*- coding: utf-8 -*-
"""Cảnh báo trượt tiến độ: đúng ngưỡng, chỉ đầu chuỗi, không nhân bản."""
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'rp_schedule_alert')
class TestScheduleAlert(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.project = cls.env['re.project'].create({
            'name': 'Proj-AL', 'code': 'AL',
            'expected_handover_date': '2026-03-01'})
        cls.subzone = cls.env['re.subzone'].create({
            'name': 'SZ-AL', 'project_id': cls.project.id, 'code': 'SZ'})
        cls.structure = cls.env['rp.structure'].create({
            'name': 'HM-AL', 'project_id': cls.project.id,
            'subzone_id': cls.subzone.id,
            'structure_level': 'item', 'structure_type': 'tower'})
        cls.package = cls.env['rp.tender.package'].create({
            'name': 'GT-AL', 'project_id': cls.project.id})
        cls.env['rp.tender.package.line'].create({
            'package_id': cls.package.id, 'structure_id': cls.structure.id})
        cls.c1 = cls._contract('HD-AL-1', 'NT-AL-1')
        cls.c2 = cls._contract('HD-AL-2', 'NT-AL-2')
        # Chuỗi ba việc, việc đầu trượt 10 ngày so kế hoạch gốc và kéo
        # theo hai việc sau trượt đúng 10 ngày — một vấn đề, không phải ba.
        cls.t1 = cls._task(cls.c1, '1', 'Việc gốc trượt',
                           '2026-01-01', '2026-01-20', bl_end='2026-01-10')
        cls.t2 = cls._task(cls.c1, '2', 'Việc kế thừa trượt',
                           '2026-01-21', '2026-01-31', bl_end='2026-01-21',
                           preds=cls.t1)
        cls.t3 = cls._task(cls.c2, '1', 'Việc của HĐ khác',
                           '2026-02-01', '2026-02-20', bl_end='2026-02-10',
                           preds=cls.t2)
        cls.Alert = cls.env['rp.schedule.alert']

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
    def _task(cls, contract, wbs, name, start, end, bl_end=None, preds=None):
        return cls.env['project.task'].create({
            'name': name,
            'project_id': contract._get_or_create_schedule_project().id,
            'rp_contract_id': contract.id, 'wbs_code': wbs,
            'planned_start': start, 'planned_end': end,
            'baseline_start': start, 'baseline_end': bl_end or end,
            'predecessor_ids': [(6, 0, preds.ids)] if preds else False,
        })

    def _alerts(self, atype=None):
        dom = [('project_id', '=', self.project.id)]
        if atype:
            dom.append(('alert_type', '=', atype))
        return self.Alert.search(dom)

    def test_chi_bao_dau_chuoi(self):
        """Ba việc cùng trượt 10 ngày → MỘT cảnh báo ở việc gốc."""
        self.project.action_scan_alerts()
        slips = self._alerts('task_slip')
        self.assertEqual(len(slips), 1, 'chỉ đầu chuỗi mới được báo')
        self.assertEqual(slips.task_id, self.t1)
        self.assertEqual(slips.days_value, 10)
        self.assertIn('Kéo theo 2 việc', slips.description)

    def test_nguong_theo_du_an(self):
        """Nâng ngưỡng cao hơn mức trượt thì không còn cảnh báo trượt."""
        self.project.alert_slip_days = 30
        self.project.action_scan_alerts()
        self.assertFalse(self._alerts('task_slip'))

    def test_khong_nhan_ban_va_cap_nhat_so(self):
        self.project.action_scan_alerts()
        first = self._alerts('task_slip')
        self.assertEqual(len(first), 1)
        self.t1.planned_end = '2026-01-25'      # trượt thêm 5 ngày
        self.project.action_scan_alerts()
        again = self._alerts('task_slip')
        self.assertEqual(len(again), 1, 'quét lại không tạo bản ghi mới')
        self.assertEqual(again.id, first.id)
        self.assertEqual(again.days_value, 15)

    def test_tu_dong_khi_het_dieu_kien(self):
        self.project.action_scan_alerts()
        alert = self._alerts('task_slip')
        self.assertEqual(alert.state, 'open')
        self.t1.planned_end = self.t1.baseline_end   # kéo lại đúng hạn
        self.project.action_scan_alerts()
        alert.invalidate_recordset()
        self.assertEqual(alert.state, 'resolved')
        self.assertTrue(alert.date_resolved)

    def test_canh_bao_tre_moc_phai_xong(self):
        """Dự án về đích 20/02 mà hạn 01/03 thì chưa báo; dời hạn thì báo."""
        self.project.action_scan_alerts()
        self.assertFalse(self._alerts('project_deadline'))
        self.project.expected_handover_date = '2026-02-01'
        self.project.action_scan_alerts()
        deadline = self._alerts('project_deadline')
        self.assertEqual(len(deadline), 1)
        self.assertEqual(deadline.severity, 'critical')
        self.assertEqual(deadline.days_value, 19)

    def test_canh_bao_diem_giao_mau_thuan(self):
        iface = self.env['rp.interface'].create({
            'name': 'Bàn giao mặt bằng cho HĐ 2',
            'project_id': self.project.id,
            'from_contract_id': self.c1.id,
            'to_contract_id': self.c2.id,
            'from_task_id': self.t2.id,
            'to_task_id': self.t3.id,
        })
        self.project.action_scan_alerts()
        self.assertFalse(self._alerts('interface_conflict'),
                         'đang khớp ngày thì chưa báo')
        self.t2.planned_end = '2026-02-15'   # xong SAU khi bên nhận cần
        iface.invalidate_recordset()
        self.assertTrue(iface.is_conflict)
        self.project.action_scan_alerts()
        conflict = self._alerts('interface_conflict')
        self.assertEqual(len(conflict), 1)
        self.assertEqual(conflict.interface_id, iface)

    def test_cron_quet_moi_du_an_co_lich(self):
        self.Alert._cron_scan()
        self.assertTrue(self._alerts())
