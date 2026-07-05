# -*- coding: utf-8 -*-
"""EVM engine — chỉ số kiểm soát chi phí + tiến độ theo hạng mục.

CV/CPI/EAC/ETC/VAC từ BAC (estimate_value) · EV (progress_value) ·
AC (actual_cost). Ngưỡng cảnh báo CPI: <1 cần theo dõi, <0.90 vượt chi.

PV time-phased (Phase 4): PV(t) = BAC × f(t) với f theo đường cong
kế hoạch (linear / S-curve) giữa date_planned_start → date_planned_end.
SPI = EV / PV(t), SV = EV − PV(t) — non-stored (phụ thuộc ngày hôm nay).
"""
import math

from odoo import api, fields, models

# Ngưỡng phân loại theo CPI (Cost Performance Index)
CPI_OVER = 0.90   # CPI dưới mức này = vượt chi nghiêm trọng (>~11% overrun)


def planned_fraction(t, start, end, curve='linear'):
    """f(t) ∈ [0,1] — tỷ lệ giá trị kế hoạch tích lũy tại ngày t.

    linear : tuyến tính theo thời gian.
    s_curve: 0.5 − cos(π·x)/2 — chậm đầu/cuối, nhanh giữa (chuẩn thi công).
    """
    if not start or not end or end <= start:
        return 0.0
    if t <= start:
        return 0.0
    if t >= end:
        return 1.0
    x = (t - start).days / (end - start).days
    if curve == 's_curve':
        return 0.5 - math.cos(math.pi * x) / 2.0
    return x


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

    # --- Phase 4: PV time-phased + SPI/SV ---
    planned_curve = fields.Selection(
        [('linear', 'Tuyến tính'),
         ('s_curve', 'S-curve (thi công)')],
        string='Đường cong kế hoạch', default='s_curve', required=True,
        help='Cách phân bổ giá trị kế hoạch theo thời gian giữa ngày bắt '
             'đầu/kết thúc KH. S-curve: chậm giai đoạn đầu/cuối, nhanh '
             'giữa — chuẩn thi công.')
    planned_value_today = fields.Monetary(
        string='Giá trị kế hoạch đến nay — PV(t)',
        compute='_compute_schedule_evm', currency_field='currency_id',
        help='PV(t) = BAC × f(hôm nay) theo đường cong kế hoạch. '
             'Không lưu DB (đổi theo ngày).')
    schedule_variance = fields.Monetary(
        string='Chênh tiến độ (SV)',
        compute='_compute_schedule_evm', currency_field='currency_id',
        help='SV = EV − PV(t). Âm = chậm so kế hoạch.')
    spi = fields.Float(
        string='SPI', compute='_compute_schedule_evm', digits=(16, 2),
        help='Schedule Performance Index = EV / PV(t). <1 = chậm tiến độ.')

    def _compute_schedule_evm(self):
        today = fields.Date.context_today(self)
        for rec in self:
            pv = rec.estimate_value * planned_fraction(
                today, rec.date_planned_start, rec.date_planned_end,
                rec.planned_curve)
            rec.planned_value_today = pv
            rec.schedule_variance = rec.progress_value - pv
            rec.spi = (rec.progress_value / pv) if pv else 0.0

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
