# -*- coding: utf-8 -*-
"""EVM rollup cấp dự án — tổng BAC/EV/AC + CPI/EAC/VAC + đếm hạng mục vượt chi."""
from odoo import api, fields, models

CPI_OVER = 0.90


class ReProject(models.Model):
    _inherit = 're.project'

    currency_id = fields.Many2one(
        'res.currency', string='Loại tiền',
        compute='_compute_currency_id', store=True, readonly=True)
    total_bac = fields.Monetary(
        string='Tổng ngân sách (BAC)', compute='_compute_project_evm',
        store=True, currency_field='currency_id')
    total_ev = fields.Monetary(
        string='Tổng giá trị làm ra (EV)', compute='_compute_project_evm',
        store=True, currency_field='currency_id')
    total_ac = fields.Monetary(
        string='Tổng chi phí thực (AC)', compute='_compute_project_evm',
        store=True, currency_field='currency_id')
    total_cv = fields.Monetary(
        string='Chênh chi phí (CV)', compute='_compute_project_evm',
        store=True, currency_field='currency_id')
    project_cpi = fields.Float(
        string='CPI dự án', compute='_compute_project_evm', store=True,
        digits=(16, 2))
    project_eac = fields.Monetary(
        string='Dự báo chi cuối (EAC)', compute='_compute_project_evm',
        store=True, currency_field='currency_id')
    project_vac = fields.Monetary(
        string='Chênh khi hoàn thành (VAC)', compute='_compute_project_evm',
        store=True, currency_field='currency_id')
    over_budget_count = fields.Integer(
        string='Số hạng mục vượt chi', compute='_compute_project_evm',
        store=True)
    cost_status = fields.Selection(
        [('no_data', 'Chưa đủ dữ liệu'),
         ('on_budget', 'Trong ngân sách'),
         ('watch', 'Cần theo dõi'),
         ('over', 'Vượt chi')],
        string='Trạng thái chi phí dự án',
        compute='_compute_project_evm', store=True, default='no_data')

    # --- Phase 4: schedule performance (non-stored, đổi theo ngày) ---
    total_pv_today = fields.Monetary(
        string='Giá trị kế hoạch đến nay — PV(t)',
        compute='_compute_project_schedule', currency_field='currency_id')
    total_sv = fields.Monetary(
        string='Chênh tiến độ (SV)',
        compute='_compute_project_schedule', currency_field='currency_id')
    project_spi = fields.Float(
        string='SPI dự án', compute='_compute_project_schedule',
        digits=(16, 2))

    def _compute_project_schedule(self):
        for proj in self:
            pv = sum(proj.structure_ids.mapped('planned_value_today'))
            ev = sum(proj.structure_ids.mapped('progress_value'))
            proj.total_pv_today = pv
            proj.total_sv = ev - pv
            proj.project_spi = (ev / pv) if pv else 0.0

    def _compute_currency_id(self):
        default = self.env.company.currency_id
        for proj in self:
            proj.currency_id = proj.currency_id or default

    @api.depends('structure_ids.estimate_value',
                 'structure_ids.progress_value',
                 'structure_ids.actual_cost',
                 'structure_ids.cost_status',
                 'project_cost_direct_total')
    def _compute_project_evm(self):
        for proj in self:
            structs = proj.structure_ids
            # BAC = Σ dự toán hạng mục + chi phí CẤP DỰ ÁN (quản lý dự án,
            # lán trại, bảo hiểm… — không thuộc hạng mục nào). Anh Đại chốt
            # 2026-08-10: thiếu phần này thì CTC và Nhu cầu vốn tính hụt
            # đúng bằng nó (tài liệu nghiệp vụ §3 đòi chi phí ĐỦ đến hoàn thành).
            bac = (sum(structs.mapped('estimate_value'))
                   + (proj.project_cost_direct_total or 0.0))
            ev = sum(structs.mapped('progress_value'))
            ac = sum(structs.mapped('actual_cost'))
            cpi = (ev / ac) if ac else 0.0
            eac = (bac / cpi) if cpi else bac
            proj.total_bac = bac
            proj.total_ev = ev
            proj.total_ac = ac
            proj.total_cv = ev - ac
            proj.project_cpi = cpi
            proj.project_eac = eac
            proj.project_vac = bac - eac
            proj.over_budget_count = len(
                structs.filtered(lambda s: s.cost_status == 'over'))
            if not ac or not ev:
                proj.cost_status = 'no_data'
            elif cpi >= 1.0:
                proj.cost_status = 'on_budget'
            elif cpi >= CPI_OVER:
                proj.cost_status = 'watch'
            else:
                proj.cost_status = 'over'
