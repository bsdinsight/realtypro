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
    amount_total = fields.Monetary(
        string='Tổng trả', compute='_compute_total', store=True)
    reference = fields.Char(string='Chứng từ')
    currency_id = fields.Many2one(
        related='note_id.currency_id', store=True, readonly=True)
    company_id = fields.Many2one(
        related='note_id.company_id', store=True, readonly=True)

    @api.depends('amount_principal', 'amount_interest')
    def _compute_total(self):
        for rec in self:
            rec.amount_total = rec.amount_principal + rec.amount_interest

    @api.constrains('amount_principal', 'amount_interest', 'note_id')
    def _check_amounts(self):
        for rec in self:
            if rec.amount_principal < 0 or rec.amount_interest < 0:
                raise ValidationError(_("Số tiền trả không được âm."))
            if rec.amount_principal == 0 and rec.amount_interest == 0:
                raise ValidationError(_(
                    "Phải nhập số tiền trả gốc hoặc trả lãi."))
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
        return recs

    def write(self, vals):
        res = super().write(vals)
        self.note_id._update_payment_state()
        return res

    def unlink(self):
        notes = self.note_id
        res = super().unlink()
        notes._update_payment_state()
        return res
