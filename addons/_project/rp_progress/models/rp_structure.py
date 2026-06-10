# -*- coding: utf-8 -*-
"""Bridge: % tiến độ + tình trạng hạng mục rolled-up từ BBN approved."""
from datetime import date

from odoo import api, fields, models


class RpStructure(models.Model):
    _inherit = 'rp.structure'

    # --- Tiến độ kế hoạch ---
    date_planned_start = fields.Date(
        string='Ngày bắt đầu KH', tracking=True)
    date_planned_end = fields.Date(
        string='Ngày kết thúc KH', tracking=True)

    # --- Tiến độ thực tế (rolled-up từ BBN approved) ---
    acceptance_line_ids = fields.One2many(
        'rp.progress.acceptance.line', 'structure_id',
        string='Khối lượng đã nghiệm thu')
    progress_value = fields.Monetary(
        string='Giá trị nghiệm thu',
        compute='_compute_progress', store=True,
        help='Σ amount_to_date của các dòng BBN approved trên hạng mục.')
    estimate_value = fields.Monetary(
        string='Giá trị dự toán',
        compute='_compute_estimate_value', store=True)
    progress_percent = fields.Float(
        string='% hoàn thành',
        compute='_compute_progress', store=True,
        help='= progress_value / estimate_value × 100.')
    date_actual_start = fields.Date(
        string='Ngày bắt đầu thực tế',
        compute='_compute_progress', store=True,
        help='Ngày BBN đầu tiên có KL trên hạng mục này.')
    date_actual_end = fields.Date(
        string='Ngày hoàn thành thực tế',
        compute='_compute_progress', store=True,
        help='Ngày BBN khiến progress đạt 100%.')
    status = fields.Selection(
        [('not_started', 'Chưa khởi công'),
         ('in_progress', 'Đang thi công'),
         ('completed', 'Hoàn thành'),
         ('delayed', 'Chậm tiến độ'),
         ('paused', 'Tạm dừng')],
        string='Trạng thái thi công',
        compute='_compute_status', store=True,
        default='not_started')
    is_delayed = fields.Boolean(
        compute='_compute_status', store=True)
    days_delayed = fields.Integer(
        compute='_compute_status', store=True)

    currency_id = fields.Many2one(
        'res.currency', string='Loại tiền',
        default=lambda self: self.env.company.currency_id,
        readonly=True)

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends('acceptance_line_ids',
                 'acceptance_line_ids.amount_to_date',
                 'acceptance_line_ids.state',
                 'acceptance_line_ids.acceptance_id.date_approved')
    def _compute_progress(self):
        for rec in self:
            approved_lines = rec.acceptance_line_ids.filtered(
                lambda l: l.state == 'approved')
            rec.progress_value = sum(approved_lines.mapped('amount_to_date'))
            # % = progress_value / estimate_value
            if rec.estimate_value:
                rec.progress_percent = min(
                    rec.progress_value / rec.estimate_value * 100.0,
                    100.0)
            else:
                rec.progress_percent = 0.0
            # Ngày bắt đầu = BBN đầu tiên có KL
            dates_started = approved_lines.filtered(
                lambda l: l.quantity_this_period > 0
            ).mapped('acceptance_id.date_approved')
            rec.date_actual_start = min(dates_started) if dates_started else False
            # Ngày kết thúc = BBN khiến progress đạt 100%
            if rec.progress_percent >= 100.0 and dates_started:
                rec.date_actual_end = max(dates_started)
            else:
                rec.date_actual_end = False

    @api.depends()
    def _compute_estimate_value(self):
        # Tính tổng giá trị dự toán của hạng mục từ rp.structure.estimate.line
        EstLine = self.env['rp.structure.estimate.line']
        for rec in self:
            lines = EstLine.search([('structure_id', '=', rec.id)])
            total = 0.0
            for el in lines:
                # estimate line có thể tên field khác — fallback
                if hasattr(el, 'amount'):
                    total += el.amount or 0.0
                elif hasattr(el, 'subtotal'):
                    total += el.subtotal or 0.0
            rec.estimate_value = total

    @api.depends('progress_percent', 'date_planned_end',
                 'date_planned_start', 'date_actual_start')
    def _compute_status(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.progress_percent >= 100.0:
                rec.status = 'completed'
                rec.is_delayed = False
                rec.days_delayed = 0
            elif rec.progress_percent > 0:
                # Đang thi công
                if (rec.date_planned_end and today > rec.date_planned_end):
                    rec.status = 'delayed'
                    rec.is_delayed = True
                    rec.days_delayed = (today - rec.date_planned_end).days
                else:
                    rec.status = 'in_progress'
                    rec.is_delayed = False
                    rec.days_delayed = 0
            else:
                # Chưa khởi công — check trễ kế hoạch khởi công
                if (rec.date_planned_start
                        and today > rec.date_planned_start):
                    rec.status = 'delayed'
                    rec.is_delayed = True
                    rec.days_delayed = (
                        today - rec.date_planned_start).days
                else:
                    rec.status = 'not_started'
                    rec.is_delayed = False
                    rec.days_delayed = 0
