# -*- coding: utf-8 -*-
"""EVM engine — chỉ số kiểm soát chi phí theo hạng mục.

CV/CPI/EAC/ETC/VAC từ BAC (estimate_value) · EV (progress_value) ·
AC (actual_cost). Ngưỡng cảnh báo CPI: <1 cần theo dõi, <0.90 vượt chi.
"""
from odoo import api, fields, models

# Ngưỡng phân loại theo CPI (Cost Performance Index)
CPI_OVER = 0.90   # CPI dưới mức này = vượt chi nghiêm trọng (>~11% overrun)


class RpStructure(models.Model):
    _inherit = 'rp.structure'

    # BAC = estimate_value, EV = progress_value, AC = actual_cost (đã có)
    cost_variance = fields.Monetary(
        string='Chênh chi phí (CV)',
        compute='_compute_evm', store=True, currency_field='currency_id',
        help='CV = EV − AC. Âm = đã chi nhiều hơn giá trị làm ra (vượt chi).')
    cpi = fields.Float(
        string='CPI', compute='_compute_evm', store=True, digits=(16, 2),
        help='Cost Performance Index = EV / AC. <1 = vượt chi; '
             '=1 đúng ngân sách; >1 tiết kiệm.')
    estimate_at_completion = fields.Monetary(
        string='Dự báo chi phí cuối (EAC)',
        compute='_compute_evm', store=True, currency_field='currency_id',
        help='EAC = BAC / CPI (nếu có CPI), else BAC. Dự báo tổng chi khi '
             'hoàn thành theo hiệu suất hiện tại.')
    estimate_to_complete = fields.Monetary(
        string='Chi phí còn lại (ETC)',
        compute='_compute_evm', store=True, currency_field='currency_id',
        help='ETC = EAC − AC. Dự báo còn phải chi.')
    variance_at_completion = fields.Monetary(
        string='Chênh khi hoàn thành (VAC)',
        compute='_compute_evm', store=True, currency_field='currency_id',
        help='VAC = BAC − EAC. Âm = dự báo vượt ngân sách khi hoàn thành.')
    cost_status = fields.Selection(
        [('no_data', 'Chưa đủ dữ liệu'),
         ('on_budget', 'Trong ngân sách'),
         ('watch', 'Cần theo dõi'),
         ('over', 'Vượt chi')],
        string='Trạng thái chi phí',
        compute='_compute_evm', store=True, default='no_data')
    cost_alert = fields.Boolean(
        string='Cảnh báo vượt chi',
        compute='_compute_evm', store=True,
        help='True khi CPI dưới ngưỡng (cần theo dõi hoặc vượt chi).')

    @api.depends('estimate_value', 'progress_value', 'actual_cost')
    def _compute_evm(self):
        for rec in self:
            bac = rec.estimate_value
            ev = rec.progress_value
            ac = rec.actual_cost
            cpi = (ev / ac) if ac else 0.0
            eac = (bac / cpi) if cpi else bac
            rec.cost_variance = ev - ac
            rec.cpi = cpi
            rec.estimate_at_completion = eac
            rec.estimate_to_complete = eac - ac
            rec.variance_at_completion = bac - eac
            # Phân loại + cờ cảnh báo
            if not ac or not ev:
                rec.cost_status = 'no_data'
                rec.cost_alert = False
            elif cpi >= 1.0:
                rec.cost_status = 'on_budget'
                rec.cost_alert = False
            elif cpi >= CPI_OVER:
                rec.cost_status = 'watch'
                rec.cost_alert = True
            else:
                rec.cost_status = 'over'
                rec.cost_alert = True
