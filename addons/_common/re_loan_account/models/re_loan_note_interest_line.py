# -*- coding: utf-8 -*-
"""
Post bút toán dồn tích lãi: Nợ (Capitalized + Expense) / Có Lãi phải trả.

Capitalization ratio đọc từ rp_loan_bridge (allocation tới cost_category).
Phần capitalize → TK 241 (XDCB), phần còn lại → TK 635 (CP lãi).
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ReLoanNoteInterestLine(models.Model):
    _inherit = 're.loan.note.interest.line'

    move_id = fields.Many2one(
        'account.move', string='Bút toán', readonly=True, copy=False)
    capitalized_amount = fields.Monetary(
        string='Phần lãi capitalize', readonly=True,
        help='Phần lãi vào TK XDCB dở dang (TK 241).')
    expense_amount = fields.Monetary(
        string='Phần lãi vào CP', readonly=True,
        help='Phần lãi vào CP lãi vay (TK 635).')
    is_posted = fields.Boolean(
        compute='_compute_is_posted', store=True)

    @api.depends('move_id', 'move_id.state')
    def _compute_is_posted(self):
        for rec in self:
            rec.is_posted = bool(rec.move_id) and rec.move_id.state == 'posted'

    def action_post_accrual(self):
        for rec in self:
            if rec.move_id:
                raise UserError(_("Dòng lãi đã có bút toán %s.",
                                  rec.move_id.name))
            if not rec.interest_amount:
                raise UserError(_("Lãi = 0, không cần post."))
            note = rec.note_id
            ratio = note._capitalization_ratio()
            total = rec.interest_amount
            capitalized = total * ratio
            expense = total - capitalized
            payable_acc = note._get_loan_account(
                'loan_account_interest_payable_id')
            journal = note._get_loan_journal()
            lines = []
            if capitalized > 0:
                cap_acc = note._get_loan_account(
                    'loan_account_interest_capitalized_id')
                lines.append((0, 0, {
                    'account_id': cap_acc.id,
                    'name': _('Lãi capitalize %(kw)s — kỳ %(p)s',
                              kw=note.name, p=rec.period_no),
                    'debit': capitalized, 'credit': 0.0,
                    'partner_id': note.partner_id.id or False,
                }))
            if expense > 0:
                exp_acc = note._get_loan_account(
                    'loan_account_interest_expense_id')
                lines.append((0, 0, {
                    'account_id': exp_acc.id,
                    'name': _('CP lãi %(kw)s — kỳ %(p)s',
                              kw=note.name, p=rec.period_no),
                    'debit': expense, 'credit': 0.0,
                    'partner_id': note.partner_id.id or False,
                }))
            lines.append((0, 0, {
                'account_id': payable_acc.id,
                'name': _('Lãi phải trả %(kw)s — kỳ %(p)s',
                          kw=note.name, p=rec.period_no),
                'debit': 0.0, 'credit': total,
                'partner_id': note.partner_id.id or False,
            }))
            move = rec.env['account.move'].create({
                'journal_id': journal.id,
                'date': rec.date_to,
                'partner_id': note.partner_id.id or False,
                'ref': _('Dồn tích lãi %(kw)s kỳ %(p)s',
                         kw=note.name, p=rec.period_no),
                'company_id': note.company_id.id,
                'loan_note_id': note.id,
                'line_ids': lines,
            })
            move.action_post()
            rec.write({
                'move_id': move.id,
                'capitalized_amount': capitalized,
                'expense_amount': expense,
                'state': 'accrued',
            })
        return True
