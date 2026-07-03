# -*- coding: utf-8 -*-
"""Dòng cấn trừ Tạm ứng vào Hóa đơn (vendor bill).

1 Tạm ứng có thể cấn trừ NHIỀU lần vào N hóa đơn:
  rp.advance.payment (1) ── (N) rp.advance.settlement (N) ── (1) account.move

Constraint:
  - amount ≤ MIN(advance.amount_remaining, invoice.amount_residual)
  - invoice phải = vendor bill (in_invoice/in_refund) + state = posted
  - invoice.partner phải = advance.partner (cấn trừ chỉ trong cùng partner)
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class RpAdvanceSettlement(models.Model):
    _name = 'rp.advance.settlement'
    _description = 'Cấn trừ Tạm ứng vào Hóa đơn'
    _order = 'date desc, id desc'

    advance_id = fields.Many2one(
        'rp.advance.payment', string='Tạm ứng',
        required=True, ondelete='cascade')
    invoice_id = fields.Many2one(
        'account.move', string='Hóa đơn',
        required=True, ondelete='restrict',
        domain="[('move_type', 'in', ['in_invoice', 'in_refund']),"
               " ('state', '=', 'posted'),"
               " ('payment_state', 'in', ('not_paid', 'partial')),"
               " ('partner_id', '=', advance_partner_id)]",
        help='Hóa đơn vendor bill cần cấn trừ. Chỉ hiện hóa đơn '
             'cùng Bên nhận tạm ứng + đã posted + CHƯA thanh toán '
             'hết (bug #22 CC1 — hóa đơn Paid không còn gì để cấn).')

    amount = fields.Monetary(
        string='Số tiền cấn trừ', required=True,
        help='Số tiền cấn trừ kỳ này. KHÔNG vượt số tạm ứng còn lại '
             'và KHÔNG vượt số hóa đơn còn lại.')
    date = fields.Date(
        string='Ngày cấn trừ', required=True,
        default=fields.Date.context_today)
    note = fields.Text(string='Ghi chú')
    user_id = fields.Many2one(
        'res.users', string='Người cấn trừ',
        default=lambda self: self.env.user, required=True)

    # Related/computed cho UX
    advance_partner_id = fields.Many2one(
        'res.partner', related='advance_id.partner_id',
        store=True, readonly=True, string='Bên nhận tạm ứng')
    advance_state = fields.Selection(
        related='advance_id.state', store=True, readonly=True)
    advance_amount_remaining = fields.Monetary(
        related='advance_id.amount_remaining', readonly=True,
        string='Tạm ứng còn lại')
    invoice_amount_total = fields.Monetary(
        related='invoice_id.amount_total', readonly=True,
        string='Giá trị hóa đơn')
    invoice_amount_residual = fields.Monetary(
        related='invoice_id.amount_residual', readonly=True,
        string='Hóa đơn chưa thanh toán')

    currency_id = fields.Many2one(
        related='advance_id.currency_id', store=True, readonly=True)
    company_id = fields.Many2one(
        related='advance_id.company_id', store=True, readonly=True)

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------
    @api.constrains('amount', 'advance_id', 'invoice_id')
    def _check_amount(self):
        for rec in self:
            if rec.amount <= 0:
                raise ValidationError(_(
                    "Số tiền cấn trừ phải > 0."))
            # Check tạm ứng còn lại (tính excluding chính dòng này)
            other_settled = sum(
                s.amount for s in rec.advance_id.settlement_ids
                if s.id != rec.id)
            advance_remaining = rec.advance_id.amount - other_settled
            if rec.amount > advance_remaining + 0.01:
                raise ValidationError(_(
                    "Số tiền cấn trừ (%(amt)s ₫) vượt quá Tạm ứng còn "
                    "lại (%(rem)s ₫).",
                    amt='{:,.0f}'.format(rec.amount),
                    rem='{:,.0f}'.format(advance_remaining)))
            # Check invoice còn lại
            invoice_residual = rec.invoice_id.amount_residual
            if rec.amount > invoice_residual + 0.01:
                raise ValidationError(_(
                    "Số tiền cấn trừ (%(amt)s ₫) vượt quá Hóa đơn "
                    "chưa thanh toán (%(rem)s ₫).",
                    amt='{:,.0f}'.format(rec.amount),
                    rem='{:,.0f}'.format(invoice_residual)))

    @api.constrains('advance_id')
    def _check_advance_state(self):
        for rec in self:
            if rec.advance_id.state not in ('paid', 'settled'):
                raise ValidationError(_(
                    "Chỉ cấn trừ được Tạm ứng đã thanh toán. Tạm ứng "
                    "%(n)s đang ở trạng thái %(s)s.",
                    n=rec.advance_id.name,
                    s=rec.advance_id.state))

    # ------------------------------------------------------------------
    # CRUD — trigger _check_fully_settled trên Tạm ứng
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records.mapped('advance_id')._check_fully_settled()
        return records

    def write(self, vals):
        res = super().write(vals)
        if 'amount' in vals or 'advance_id' in vals:
            self.mapped('advance_id')._check_fully_settled()
        return res

    def unlink(self):
        advances = self.mapped('advance_id')
        res = super().unlink()
        # Sau khi xoá dòng cấn trừ → có thể quay về paid nếu đang settled
        for adv in advances:
            if adv.state == 'settled' and adv.amount_remaining > 0.01:
                adv.state = 'paid'
                adv.date_settled = False
                adv.message_post(body=_(
                    "Xoá dòng cấn trừ → còn lại %(r)s ₫, quay về "
                    "trạng thái 'Đã thanh toán'.",
                    r='{:,.0f}'.format(adv.amount_remaining)))
        return res
