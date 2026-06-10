# -*- coding: utf-8 -*-
"""Post bút toán giải ngân: Nợ Bank / Có Loan."""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ReLoanNoteDisbursement(models.Model):
    _inherit = 're.loan.note.disbursement'

    move_id = fields.Many2one(
        'account.move', string='Bút toán', readonly=True, copy=False,
        help='Bút toán account.move đã post cho giải ngân này.')
    is_posted = fields.Boolean(
        string='Đã post', compute='_compute_is_posted', store=True)

    @api.depends('move_id', 'move_id.state')
    def _compute_is_posted(self):
        for rec in self:
            rec.is_posted = bool(rec.move_id) and rec.move_id.state == 'posted'

    def action_post_journal_entry(self):
        for rec in self:
            if rec.move_id:
                raise UserError(_(
                    "Giải ngân này đã có bút toán %s.", rec.move_id.name))
            note = rec.note_id
            bank_acc = note._get_loan_account('loan_account_bank_id')
            loan_acc = note._get_loan_account('loan_account_principal_id')
            journal = note._get_loan_journal()
            move = rec.env['account.move'].create({
                'journal_id': journal.id,
                'date': rec.date,
                'partner_id': note.partner_id.id or False,
                'ref': _('Giải ngân %(kw)s — %(ref)s',
                         kw=note.name, ref=rec.reference or rec.date),
                'company_id': note.company_id.id,
                'loan_note_id': note.id,
                'line_ids': [
                    (0, 0, {
                        'account_id': bank_acc.id,
                        'name': _('GN %s', note.name),
                        'debit': rec.amount, 'credit': 0.0,
                        'partner_id': note.partner_id.id or False,
                    }),
                    (0, 0, {
                        'account_id': loan_acc.id,
                        'name': _('Vay %s', note.name),
                        'debit': 0.0, 'credit': rec.amount,
                        'partner_id': note.partner_id.id or False,
                    }),
                ],
            })
            move.action_post()
            rec.move_id = move.id
        return True
