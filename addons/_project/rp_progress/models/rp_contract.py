# -*- coding: utf-8 -*-
"""Bridge: thêm BBNT KLCV + SLA + rolled-up % progress vào rp.contract."""
from odoo import api, fields, models


class RpContract(models.Model):
    _inherit = 'rp.contract'

    # --- SLA trả lời BBN ---
    sla_response_days = fields.Integer(
        string='SLA trả lời BBN (ngày)', default=7,
        help='Số ngày CĐT/tổng thầu phải duyệt BBN sau khi NT đề xuất. '
             'Hệ thống cảnh báo nếu trễ. Đặt 0 để tắt SLA.')

    # --- BBN list + counts ---
    acceptance_ids = fields.One2many(
        'rp.progress.acceptance', 'contract_id',
        string='BBNT nghiệm thu')
    acceptance_count = fields.Integer(
        string='Số BBNT', compute='_compute_acceptance_stats')

    # --- Rolled-up từ BBN approved ---
    acceptance_value_to_date = fields.Monetary(
        string='Giá trị nghiệm thu lũy kế',
        compute='_compute_acceptance_stats', store=True,
        help='Tổng giá trị nghiệm thu của các BBN ĐÃ DUYỆT.')
    acceptance_progress_percent = fields.Float(
        string='% nghiệm thu',
        compute='_compute_acceptance_stats', store=True,
        help='= acceptance_value_to_date / contract_value_pretax × 100.')

    @api.depends('acceptance_ids', 'acceptance_ids.state',
                 'acceptance_ids.total_value_period',
                 'contract_value_pretax')
    def _compute_acceptance_stats(self):
        for rec in self:
            rec.acceptance_count = len(rec.acceptance_ids)
            approved = rec.acceptance_ids.filtered(
                lambda a: a.state == 'approved')
            value = sum(approved.mapped('total_value_period'))
            rec.acceptance_value_to_date = value
            if rec.contract_value_pretax:
                rec.acceptance_progress_percent = (
                    value / rec.contract_value_pretax * 100.0)
            else:
                rec.acceptance_progress_percent = 0.0

    def action_view_acceptances(self):
        self.ensure_one()
        return {
            'name': 'BBNT nghiệm thu — %s' % self.name,
            'type': 'ir.actions.act_window',
            'target': 'new',
            'res_model': 'rp.progress.acceptance',
            'view_mode': 'list,form',
            'domain': [('contract_id', '=', self.id)],
            'context': {
                'default_contract_id': self.id,
            },
        }
