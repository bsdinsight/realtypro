# -*- coding: utf-8 -*-
"""Inherit rp.loan.disbursement.dossier: pick Tạm ứng thay Hóa đơn.

Use case: KW giải ngân để THANH TOÁN TẠM ỨNG cho HĐ nhà thầu/NCC
TRƯỚC khi có hóa đơn. Lúc này Hồ sơ giải ngân pick advance_payment_id
thay vì invoice_id.

Validation:
  - Pick MỘT trong hai: invoice_id HOẶC advance_payment_id
  - Nếu pick advance: state advance phải = 'approved' (đã duyệt)
  - amount dossier ≤ advance.amount

Khi KW activate: nếu dossier có advance_payment_id → set
advance state = 'paid' (xử lý trong re_loan_note_inherit.py).
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class RpLoanDisbursementDossier(models.Model):
    _inherit = 'rp.loan.disbursement.dossier'

    advance_payment_id = fields.Many2one(
        'rp.advance.payment', string='Tạm ứng',
        domain="[('state', 'in', ('approved', 'partial_paid')),"
               " ('partner_id', '=', disbursement_beneficiary_id)]",
        help='Tạm ứng cần giải ngân (chưa có hóa đơn). Pick cái này '
             'THAY VÌ "Hóa đơn" — chỉ chọn 1 trong 2. Chỉ hiện Tạm '
             'ứng đã được phê duyệt (state=approved) của đúng nhà '
             'thầu (Bên nhận tiền trên giải ngân).')

    advance_amount_total = fields.Monetary(
        string='Giá trị tạm ứng',
        related='advance_payment_id.amount',
        store=False, readonly=True)

    is_advance_payment = fields.Boolean(
        string='Là thanh toán tạm ứng',
        compute='_compute_is_advance_payment',
        store=True,
        help='True nếu hồ sơ này pick Tạm ứng (chưa có hóa đơn).')

    @api.depends('advance_payment_id')
    def _compute_is_advance_payment(self):
        for rec in self:
            rec.is_advance_payment = bool(rec.advance_payment_id)

    @api.onchange('advance_payment_id')
    def _onchange_advance_fill_amount(self):
        """Pick Tạm ứng → auto-fill = phần CHƯA thanh toán (bug #19:
        thanh toán từng phần qua nhiều dossier — không fill full)."""
        if self.advance_payment_id:
            self.amount = self.advance_payment_id.amount_unpaid
            # Clear invoice nếu đang pick (mutual exclusive)
            self.invoice_id = False

    @api.onchange('invoice_id')
    def _onchange_invoice_clear_advance(self):
        """Pick invoice → clear advance (mutual exclusive)."""
        if self.invoice_id:
            self.advance_payment_id = False

    @api.constrains('invoice_id', 'advance_payment_id')
    def _check_one_target(self):
        for rec in self:
            if rec.invoice_id and rec.advance_payment_id:
                raise ValidationError(_(
                    "Hồ sơ giải ngân: chỉ chọn 1 trong 2 — Hóa đơn "
                    "HOẶC Tạm ứng. KHÔNG chọn cả hai."))

    @api.constrains('amount', 'advance_payment_id')
    def _check_advance_amount(self):
        for rec in self:
            if not rec.advance_payment_id:
                continue
            if rec.amount > rec.advance_payment_id.amount + 0.01:
                raise ValidationError(_(
                    "Số tiền dossier (%(amt)s ₫) vượt quá giá trị "
                    "Tạm ứng %(n)s (%(adv)s ₫).",
                    amt='{:,.0f}'.format(rec.amount),
                    n=rec.advance_payment_id.name,
                    adv='{:,.0f}'.format(rec.advance_payment_id.amount)))
