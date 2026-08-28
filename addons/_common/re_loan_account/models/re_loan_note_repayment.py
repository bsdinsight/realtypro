# -*- coding: utf-8 -*-
"""
Post bút toán trả nợ: Nợ Vay (gốc) + Nợ Lãi phải trả (lãi) / Có Bank.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ReLoanNoteRepayment(models.Model):
    _inherit = 're.loan.note.repayment'

    move_id = fields.Many2one(
        'account.move', string='Bút toán', readonly=True, copy=False)
    is_posted = fields.Boolean(
        compute='_compute_is_posted', store=True)

    @api.depends('move_id', 'move_id.state')
    def _compute_is_posted(self):
        for rec in self:
            rec.is_posted = bool(rec.move_id) and rec.move_id.state == 'posted'

    def action_post_journal_entry(self):
        for rec in self:
            if rec.move_id:
                raise UserError(_("Trả nợ này đã có bút toán %s.",
                                  rec.move_id.name))
            if rec.amount_total <= 0:
                raise UserError(_("Số tiền = 0, không cần post."))
            note = rec.note_id
            journal = note._get_loan_journal()
            bank_acc = note._get_loan_account('loan_account_bank_id')
            lines = []
            if rec.amount_principal > 0:
                loan_acc = note._get_loan_account(
                    'loan_account_principal_id')
                lines.append(note._fx_line(
                    loan_acc, _('Trả gốc %s', note.name),
                    rec.amount_principal, rec.date, debit=True))
            if rec.amount_interest > 0:
                payable_acc = note._get_loan_account(
                    'loan_account_interest_payable_id')
                lines.append(note._fx_line(
                    payable_acc, _('Trả lãi %s', note.name),
                    rec.amount_interest, rec.date, debit=True))
            # Phí nằm trong amount_total nhưng không có dòng riêng ở bản
            # gốc; vế tiền lấy đúng tổng các vế trên nên không lệch.
            lines.append(note._fx_balance_line(
                bank_acc, _('Trả nợ %s', note.name),
                lines, rec.date, debit=False))
            move = rec.env['account.move'].create({
                'journal_id': journal.id,
                'date': rec.date,
                'partner_id': note.partner_id.id or False,
                'ref': _('Trả nợ %(kw)s — %(ref)s',
                         kw=note.name, ref=rec.reference or rec.date),
                'company_id': note.company_id.id,
                'loan_note_id': note.id,
                'line_ids': lines,
            })
            move.action_post()
            rec.move_id = move.id
        return True
