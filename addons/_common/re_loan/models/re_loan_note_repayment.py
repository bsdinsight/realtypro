# -*- coding: utf-8 -*-
"""Trả nợ (repayment) — một lần trả gốc và/hoặc lãi cho một KW."""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ReLoanNoteRepayment(models.Model):
    _name = 're.loan.note.repayment'
    _description = 'Trả nợ khế ước'
    _order = 'date, id'

    note_id = fields.Many2one(
        're.loan.note', string='Khế ước', required=True, ondelete='cascade')
    date = fields.Date(
        string='Ngày trả', required=True, default=fields.Date.context_today)
    amount_principal = fields.Monetary(string='Trả gốc', default=0.0)
    amount_interest = fields.Monetary(string='Trả lãi', default=0.0)
    amount_fee = fields.Monetary(
        string='Trả phí', default=0.0,
        help='Phí KW phân bổ kỳ (khách hàng #9).')
    amount_total = fields.Monetary(
        string='Tổng trả', compute='_compute_total', store=True)
    reference = fields.Char(string='Chứng từ')
    bank_account_id = fields.Many2one(
        'res.partner.bank', string='Tài khoản thanh toán',
        domain="[('partner_id', '=', company_partner_id)]",
        help='TK NH của doanh nghiệp dùng để trả nợ đợt này (khách hàng #24).')
    company_partner_id = fields.Many2one(
        'res.partner', related='company_id.partner_id', readonly=True)
    # --- Link tới kỳ lãi cụ thể (tracking allocation) ---
    interest_line_id = fields.Many2one(
        're.loan.note.interest.line', string='Kỳ thanh toán',
        ondelete='set null',
        domain="[('note_id', '=', note_id)]",
        help='Kỳ lãi mà repayment này thanh toán. NULL = repayment '
             'cũ chưa allocate vào kỳ cụ thể (chỉ track ở note level).')
    bank_advice_line_id = fields.Many2one(
        're.loan.bank.advice.line', string='Dòng giấy báo nợ NH',
        ondelete='set null', readonly=True,
        help='Repayment auto-tạo từ giấy báo nợ ngân hàng trích thu '
             'tự động (re.loan.bank.advice).')
    is_auto_debit = fields.Boolean(
        string='Trích thu tự động', readonly=True,
        compute='_compute_is_auto_debit', store=True)
    currency_id = fields.Many2one(
        related='note_id.currency_id', store=True, readonly=True)
    company_id = fields.Many2one(
        related='note_id.company_id', store=True, readonly=True)

    @api.depends('bank_advice_line_id')
    def _compute_is_auto_debit(self):
        for rec in self:
            rec.is_auto_debit = bool(rec.bank_advice_line_id)

    @api.onchange('note_id')
    def _onchange_default_bank_account(self):
        for rec in self:
            if not rec.bank_account_id and rec.company_id.partner_id:
                banks = rec.company_id.partner_id.bank_ids
                rec.bank_account_id = banks[:1] if banks else False

    @api.depends('amount_principal', 'amount_interest', 'amount_fee')
    def _compute_total(self):
        for rec in self:
            rec.amount_total = (rec.amount_principal + rec.amount_interest
                                + rec.amount_fee)

    @api.constrains('amount_principal', 'amount_interest', 'amount_fee',
                    'note_id')
    def _check_amounts(self):
        for rec in self:
            if rec.amount_principal < 0 or rec.amount_interest < 0 \
                    or rec.amount_fee < 0:
                raise ValidationError(_("Số tiền trả không được âm."))
            if rec.amount_principal == 0 and rec.amount_interest == 0 \
                    and rec.amount_fee == 0:
                raise ValidationError(_(
                    "Phải nhập số tiền trả gốc, trả lãi hoặc trả phí."))
            note = rec.note_id
            total_principal = sum(note.repayment_ids.mapped('amount_principal'))
            if total_principal > note.amount_disbursed:
                raise ValidationError(_(
                    "Tổng trả gốc (%(t)s) vượt số đã giải ngân của KW "
                    "'%(n)s' (%(d)s).",
                    t=total_principal, n=note.name, d=note.amount_disbursed))

    # ------------------------------------------------------------------
    # Cập nhật lifecycle KW
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        recs.note_id._update_payment_state()
        # Trigger recompute interest_line paid/state nếu có link
        recs.mapped('interest_line_id')._compute_paid_amounts()
        return recs

    def write(self, vals):
        old_lines = self.mapped('interest_line_id')
        res = super().write(vals)
        self.note_id._update_payment_state()
        (old_lines | self.mapped('interest_line_id'))._compute_paid_amounts()
        return res

    def unlink(self):
        notes = self.note_id
        old_lines = self.mapped('interest_line_id')
        res = super().unlink()
        notes._update_payment_state()
        old_lines._compute_paid_amounts()
        return res
