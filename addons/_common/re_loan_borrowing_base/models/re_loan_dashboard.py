# -*- coding: utf-8 -*-
"""KPI Borrowing base trên dashboard Quản lý Vay."""
from odoo import api, fields, models


class ReLoanDashboard(models.TransientModel):
    _inherit = 're.loan.dashboard'

    kpi_bb_base_total = fields.Monetary(
        string='Cơ sở bảo đảm (Σ HĐTD active)',
        help='Σ borrowing base (giá trị TSBĐ × tỷ lệ cho vay) của các '
             'HĐTD đang hiệu lực có quản TSBĐ.')
    kpi_bb_available_effective = fields.Monetary(
        string='Khả dụng thực tế',
        help='Σ khả dụng thực tế các HĐTD active = min(hạn mức, cơ sở '
             'bảo đảm) − dư nợ. Số RÚT ĐƯỢC hôm nay theo TSBĐ hiện hữu.')
    kpi_bb_margin_call = fields.Integer(
        string='Cảnh báo thiếu bảo đảm',
        help='Số facility/HĐTD có dư nợ vượt cơ sở bảo đảm (margin call).')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_hdtd = self.env['re.loan.credit.contract'].search(
            [('state', '=', 'active')])
        with_pledges = active_hdtd.filtered('has_any_pledges')
        res['kpi_bb_base_total'] = sum(
            with_pledges.mapped('borrowing_base_total') or [0])
        res['kpi_bb_available_effective'] = sum(
            active_hdtd.mapped('amount_available_effective') or [0])
        facilities = active_hdtd.mapped('facility_ids')
        res['kpi_bb_margin_call'] = (
            len(with_pledges.filtered('margin_call'))
            + len(facilities.filtered('margin_call')))
        return res

    def action_open_margin_call(self):
        """Facility đang margin call (compute non-stored → lọc python)."""
        facilities = self.env['re.loan.facility'].search([]).filtered(
            'margin_call')
        return {
            'type': 'ir.actions.act_window',
            'name': 'Facility thiếu bảo đảm (margin call)',
            'res_model': 're.loan.facility',
            'view_mode': 'list,form',
            'domain': [('id', 'in', facilities.ids)],
        }
