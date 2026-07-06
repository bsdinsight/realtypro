# -*- coding: utf-8 -*-
"""Kỳ khấu hao tài sản thuê tài chính — đường thẳng theo tháng."""
from odoo import _, api, fields, models


class ReLeaseDepreciationLine(models.Model):
    _name = 're.lease.depreciation.line'
    _description = 'Kỳ khấu hao tài sản thuê TC'
    _order = 'contract_id, sequence, id'

    contract_id = fields.Many2one(
        're.lease.contract', string='HĐ thuê', required=True,
        ondelete='cascade', index=True)
    sequence = fields.Integer(string='Kỳ', required=True)
    date = fields.Date(string='Ngày khấu hao', required=True)
    amount = fields.Monetary(string='Số tiền', required=True)
    move_id = fields.Many2one(
        'account.move', string='Bút toán', readonly=True, copy=False)
    state = fields.Selection(
        [('draft', 'Chưa ghi sổ'), ('posted', 'Đã ghi sổ')],
        compute='_compute_state', store=True, string='Trạng thái')
    currency_id = fields.Many2one(
        related='contract_id.currency_id', store=True)
    company_id = fields.Many2one(
        related='contract_id.company_id', store=True)

    @api.depends('move_id')
    def _compute_state(self):
        for line in self:
            line.state = 'posted' if line.move_id else 'draft'

    def _post_move(self):
        for line in self:
            c = line.contract_id
            move = self.env['account.move'].create({
                'move_type': 'entry',
                'journal_id': c.journal_id.id,
                'date': line.date,
                'ref': _('Khấu hao TS thuê TC %(n)s — kỳ %(k)s',
                         n=c.name, k=line.sequence),
                'line_ids': [
                    (0, 0, {'account_id':
                            c.account_depreciation_expense_id.id,
                            'name': _('CP khấu hao %(n)s kỳ %(k)s',
                                      n=c.name, k=line.sequence),
                            'debit': line.amount, 'credit': 0.0}),
                    (0, 0, {'account_id': c.account_depreciation_id.id,
                            'name': _('Hao mòn %(n)s kỳ %(k)s',
                                      n=c.name, k=line.sequence),
                            'debit': 0.0, 'credit': line.amount}),
                ],
            })
            move.action_post()
            line.move_id = move
        return True

    def action_post_move(self):
        for line in self:
            if line.move_id:
                continue
            c = line.contract_id
            if not (c.account_depreciation_expense_id
                    and c.account_depreciation_id and c.journal_id):
                from odoo.exceptions import UserError
                raise UserError(_(
                    'Khai đủ TK khấu hao + sổ nhật ký trên HĐ %(n)s.',
                    n=c.name))
            line._post_move()
        return True
