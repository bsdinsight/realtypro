# -*- coding: utf-8 -*-
"""Bản tổng hợp theo kỳ: chụp đúng số, và KHÔNG đổi theo dữ liệu sau đó."""
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'rp_report')
class TestProjectBrief(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.project = cls.env['re.project'].create({
            'name': 'Proj-BR', 'code': 'BR',
            'expected_handover_date': '2026-06-30'})
        cls.subzone = cls.env['re.subzone'].create({
            'name': 'SZ-BR', 'project_id': cls.project.id, 'code': 'SZ'})
        cls.structure = cls.env['rp.structure'].create({
            'name': 'HM-BR', 'project_id': cls.project.id,
            'subzone_id': cls.subzone.id,
            'structure_level': 'item', 'structure_type': 'tower'})
        cls.package = cls.env['rp.tender.package'].create({
            'name': 'GT-BR', 'project_id': cls.project.id})
        cls.env['rp.tender.package.line'].create({
            'package_id': cls.package.id, 'structure_id': cls.structure.id})
        partner = cls.env['res.partner'].create({
            'is_contractor': True, 'is_company': True,
            'name': 'NT-BR', 'ref': 'NT-BR'})
        cls.contract = cls.env['rp.contract'].create({
            'name': 'HD-BR', 'tender_package_id': cls.package.id,
            'contractor_id': partner.id,
            'contract_value_pretax': 1_000_000_000.0,
            'date_end': '2026-06-30'})
        cls.contract.action_sign()
        cls.task = cls.env['project.task'].create({
            'name': 'Việc chính',
            'project_id': cls.contract._get_or_create_schedule_project().id,
            'rp_contract_id': cls.contract.id, 'wbs_code': '1',
            'planned_start': '2026-01-01', 'planned_end': '2026-06-30',
            'baseline_start': '2026-01-01', 'baseline_end': '2026-05-30'})
        cls.Brief = cls.env['rp.project.brief']

    def test_chup_dung_so(self):
        brief = self.Brief._capture(self.project)
        self.project.invalidate_recordset()
        self.assertEqual(brief.task_count, self.project.schedule_task_count)
        self.assertEqual(brief.contract_count, 1)
        self.assertEqual(str(brief.forecast_end), '2026-06-30')
        self.assertEqual(brief.task_late_count, 1)      # trượt 31 ngày
        self.assertEqual(brief.committed, 1_000_000_000.0)
        self.assertEqual(brief.cost_forecast,
                         self.project.cost_forecast_total)

    def test_so_da_chot_khong_doi_theo_lich(self):
        """Báo cáo kỳ trước phải giữ nguyên số của kỳ trước."""
        brief = self.Brief._capture(self.project)
        old_forecast = brief.forecast_end
        self.task.planned_end = '2026-09-30'
        self.project.invalidate_recordset()
        brief.invalidate_recordset()
        self.assertEqual(brief.forecast_end, old_forecast)
        self.assertNotEqual(self.project.schedule_forecast_end, old_forecast)

    def test_chot_tay_tu_form_du_an(self):
        res = self.project.action_capture_brief()
        self.assertEqual(res['res_model'], 'rp.project.brief')
        self.assertTrue(self.project.brief_ids)

    def test_cron_chot_moi_du_an_co_lich(self):
        before = self.Brief.search_count(
            [('project_id', '=', self.project.id)])
        self.Brief._cron_monthly()
        after = self.Brief.search_count(
            [('project_id', '=', self.project.id)])
        self.assertEqual(after, before + 1)
