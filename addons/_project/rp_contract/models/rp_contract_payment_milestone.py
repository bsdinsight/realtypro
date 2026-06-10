# -*- coding: utf-8 -*-
"""
Lịch thanh toán HĐ nhà thầu — milestone-based.

Mỗi milestone: % giá trị HĐ (sau thuế) hoặc số tiền trực tiếp. Cập nhật
tiến độ HĐ qua field `state` (planned → invoiced → paid).
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class RpContractPaymentMilestone(models.Model):
    _name = 'rp.contract.payment.milestone'
    _description = 'Lịch thanh toán HĐ nhà thầu'
    _order = 'contract_id, sequence, id'

    contract_id = fields.Many2one(
        'rp.contract', string='HĐ', required=True, ondelete='cascade',
        index=True)
    sequence = fields.Integer(default=10)
    name = fields.Char(
        string='Mốc thanh toán', required=True,
        help='Vd: "Tạm ứng 30%", "Đợt 1: hoàn thành phần móng".')
    percent = fields.Float(
        string='% giá trị HĐ', digits=(5, 2),
        help='Tỷ lệ trên giá trị HĐ sau thuế. Để 0 nếu nhập số tiền trực tiếp.')
    amount = fields.Monetary(
        string='Số tiền', compute='_compute_amount', store=True,
        readonly=False,
        help='Tự tính từ % × giá trị HĐ sau thuế nếu có %; có thể sửa tay.')
    due_date = fields.Date(string='Ngày đến hạn')
    paid_date = fields.Date(string='Ngày trả thực tế')
    reference = fields.Char(string='Chứng từ')
    note = fields.Char(string='Ghi chú')

    state = fields.Selection(
        [('planned', 'Dự kiến'),
         ('invoiced', 'Đã xuất hoá đơn'),
         ('paid', 'Đã trả')],
        string='Trạng thái', default='planned', required=True)

    currency_id = fields.Many2one(
        related='contract_id.currency_id', store=True, readonly=True)
    company_id = fields.Many2one(
        related='contract_id.company_id', store=True, readonly=True)

    @api.depends('percent', 'contract_id.contract_value_total')
    def _compute_amount(self):
        for rec in self:
            if rec.percent:
                rec.amount = (
                    rec.contract_id.contract_value_total * rec.percent / 100.0)
            # Nếu percent = 0 và amount đã có giá trị (user nhập tay), giữ.
            elif not rec.amount:
                rec.amount = 0.0

    @api.constrains('percent', 'amount')
    def _check_values(self):
        for rec in self:
            if rec.percent < 0 or rec.percent > 100:
                raise ValidationError(_("% phải trong 0–100."))
            if rec.amount < 0:
                raise ValidationError(_("Số tiền không được âm."))

    @api.constrains('contract_id', 'percent')
    def _check_total_percent(self):
        # Σ percent của các milestone ≤ 100% (cho phép retention không có milestone).
        for rec in self:
            if not rec.contract_id:
                continue
            total = sum(rec.contract_id.payment_milestone_ids.mapped(
                'percent'))
            if total > 100.01:
                raise ValidationError(_(
                    "Tổng %% các mốc thanh toán (%(t).2f%%) vượt quá 100%%.",
                    t=total))

    # ----- Lifecycle actions ---------------------------------------------
    def action_set_invoiced(self):
        for rec in self:
            if rec.state != 'planned':
                raise UserError(_(
                    "Chỉ mốc Dự kiến mới đánh dấu Xuất hoá đơn được."))
            rec.state = 'invoiced'

    def action_set_paid(self):
        for rec in self:
            if rec.state == 'paid':
                raise UserError(_("Mốc đã trả."))
            rec.state = 'paid'
            if not rec.paid_date:
                rec.paid_date = fields.Date.context_today(rec)

    def action_reset_planned(self):
        for rec in self:
            rec.state = 'planned'
            rec.paid_date = False
