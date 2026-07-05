# -*- coding: utf-8 -*-
"""Dashboard EVM cấp dự án cho Ban QLDA — KPI + CPI theo hạng mục (đèn
giao thông) + so sánh BAC/EV/AC/EAC, render SVG server-side.
"""
from odoo import api, fields, models

from . import evm_svg


class RpEvmDashboard(models.TransientModel):
    _name = 'rp.evm.dashboard'
    _description = 'EVM — Dashboard kiểm soát chi phí'

    project_id = fields.Many2one(
        're.project', string='Dự án', required=True,
        default=lambda self: self.env['re.project'].search([], limit=1))
    currency_id = fields.Many2one(
        related='project_id.currency_id', readonly=True)

    # --- KPI (từ rollup re.project) ---
    kpi_bac = fields.Monetary(string='Ngân sách (BAC)',
                              compute='_compute_dashboard')
    kpi_ev = fields.Monetary(string='Giá trị làm ra (EV)',
                             compute='_compute_dashboard')
    kpi_ac = fields.Monetary(string='Chi phí thực (AC)',
                             compute='_compute_dashboard')
    kpi_cv = fields.Monetary(string='Chênh chi phí (CV)',
                             compute='_compute_dashboard')
    kpi_cpi = fields.Float(string='CPI dự án', digits=(16, 2),
                           compute='_compute_dashboard')
    kpi_eac = fields.Monetary(string='Dự báo chi cuối (EAC)',
                              compute='_compute_dashboard')
    kpi_vac = fields.Monetary(string='Chênh khi hoàn thành (VAC)',
                              compute='_compute_dashboard')
    kpi_progress = fields.Float(string='% hoàn thành (EV/BAC)',
                                compute='_compute_dashboard')
    kpi_over_count = fields.Integer(string='Hạng mục vượt chi',
                                    compute='_compute_dashboard')
    cost_status = fields.Selection(
        [('no_data', 'Chưa đủ dữ liệu'),
         ('on_budget', 'Trong ngân sách'),
         ('watch', 'Cần theo dõi'),
         ('over', 'Vượt chi')],
        string='Trạng thái chi phí', compute='_compute_dashboard')

    # --- Charts SVG ---
    chart_cpi_html = fields.Html(
        string='CPI theo hạng mục', compute='_compute_dashboard',
        sanitize=False)
    chart_cost_html = fields.Html(
        string='So sánh BAC / EV / AC / EAC', compute='_compute_dashboard',
        sanitize=False)

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = 'EVM — Kiểm soát chi phí'

    @api.depends('project_id')
    def _compute_dashboard(self):
        for d in self:
            p = d.project_id
            d.kpi_bac = p.total_bac
            d.kpi_ev = p.total_ev
            d.kpi_ac = p.total_ac
            d.kpi_cv = p.total_cv
            d.kpi_cpi = p.project_cpi
            d.kpi_eac = p.project_eac
            d.kpi_vac = p.project_vac
            d.kpi_over_count = p.over_budget_count
            d.cost_status = p.cost_status or 'no_data'
            d.kpi_progress = (
                (p.total_ev / p.total_bac * 100.0) if p.total_bac else 0.0)
            # CPI theo hạng mục — chỉ hạng mục có dữ liệu, xếp CPI tăng dần
            # (vượt chi nặng nhất lên đầu)
            structs = p.structure_ids.filtered(
                lambda s: s.estimate_value or s.actual_cost)
            structs = structs.sorted(
                key=lambda s: (s.cpi if s.cpi else 999.0))
            rows = [(s.display_name, s.cpi, s.cost_status) for s in structs]
            d.chart_cpi_html = evm_svg.cpi_bars(rows)
            d.chart_cost_html = evm_svg.cost_compare(
                p.total_bac, p.total_ev, p.total_ac, p.project_eac)

    def action_open_structures(self):
        """Drill-down: mở list hạng mục vượt chi của dự án."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Hạng mục — Kiểm soát chi phí',
            'res_model': 'rp.structure',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.project_id.id)],
            'context': {'search_default_cost_alert': 1},
        }
