# -*- coding: utf-8 -*-
"""Kỳ thanh toán thuê — sinh hóa đơn NCC (đi thuê) / hóa đơn bán (cho
thuê lại) từng kỳ. Thuê tài chính: 2 dòng GỐC + LÃI trên cùng hóa đơn.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ReLeasePaymentLine(models.Model):
    _name = 're.lease.payment.line'
    _description = 'Kỳ thanh toán thuê'
    _order = 'contract_id, sequence, id'

    contract_id = fields.Many2one(
        're.lease.contract', string='HĐ thuê', required=True,
        ondelete='cascade', index=True)
    sequence = fields.Integer(string='Kỳ', required=True)
    date_due = fields.Date(string='Ngày đến hạn', required=True)

    direction = fields.Selection(
        related='contract_id.direction', store=True)
    lease_type = fields.Selection(
        related='contract_id.lease_type', store=True)
    partner_id = fields.Many2one(
        related='contract_id.partner_id', store=True, string='Đối tác')
    currency_id = fields.Many2one(
        related='contract_id.currency_id', store=True)
    company_id = fields.Many2one(
        related='contract_id.company_id', store=True)

    # Tài chính
    principal_amount = fields.Monetary(string='Gốc kỳ')
    interest_amount = fields.Monetary(string='Lãi kỳ')
    balance_after = fields.Monetary(
        string='Dư nợ gốc sau kỳ', readonly=True)
    # Hoạt động
    rent_amount = fields.Monetary(string='Tiền thuê kỳ')

    amount_total = fields.Monetary(
        string='Tổng kỳ (trước thuế)',
        compute='_compute_amount_total', store=True)
    invoice_id = fields.Many2one(
        'account.move', string='Hóa đơn', readonly=True, copy=False)
    state = fields.Selection(
        [('draft', 'Chưa lên hóa đơn'),
         ('invoiced', 'Đã lên hóa đơn'),
         ('paid', 'Đã thanh toán')],
        string='Trạng thái', compute='_compute_state', store=True)

    @api.depends('principal_amount', 'interest_amount', 'rent_amount')
    def _compute_amount_total(self):
        for line in self:
            line.amount_total = (line.principal_amount
                                 + line.interest_amount
                                 + line.rent_amount)

    @api.depends('invoice_id', 'invoice_id.state',
                 'invoice_id.payment_state')
    def _compute_state(self):
        for line in self:
            inv = line.invoice_id
            if not inv or inv.state == 'cancel':
                line.state = 'draft'
            elif inv.state == 'posted' and inv.payment_state in (
                    'paid', 'in_payment', 'reversed'):
                line.state = 'paid'
            else:
                line.state = 'invoiced'

    # ------------------------------------------------------------------
    # Sinh hóa đơn kỳ
    # ------------------------------------------------------------------
    def action_create_invoice(self):
        for line in self:
            c = line.contract_id
            if c.state != 'active':
                raise UserError(_(
                    'HĐ %(n)s chưa Hiệu lực — kích hoạt trước khi lên '
                    'hóa đơn.', n=c.name))
            if line.invoice_id and line.invoice_id.state != 'cancel':
                raise UserError(_(
                    'Kỳ %(k)s đã có hóa đơn %(i)s.',
                    k=line.sequence, i=line.invoice_id.name))
            move = self.env['account.move'].create(
                line._prepare_invoice_vals())
            line.invoice_id = move
            c.message_post(body=_(
                'Kỳ %(k)s: đã tạo hóa đơn %(t)s (nháp) — %(a)s.',
                k=line.sequence,
                t=_('NCC') if c.direction == 'in' else _('bán'),
                a='{:,.0f}'.format(line.amount_total)))
        return True

    def _prepare_invoice_vals(self):
        self.ensure_one()
        c = self.contract_id
        move_type = 'in_invoice' if c.direction == 'in' else 'out_invoice'
        taxes = [(6, 0, c.tax_id.ids)] if c.tax_id else [(6, 0, [])]
        label = _('%(hd)s — kỳ %(k)s/%(n)s',
                  hd=c.name, k=self.sequence, n=c.n_periods)
        lines = []
        if c.lease_type == 'finance':
            # Dòng GỐC → TK nợ gốc (đi thuê) / TK phải thu thuê TC (cho
            # thuê lại): hóa đơn vừa là chứng từ thanh toán vừa giảm
            # nợ/phải thu gốc.
            principal_account = (c.account_liability_id
                                 if c.direction == 'in'
                                 else c.account_receivable_finance_id)
            if not principal_account:
                raise UserError(_(
                    'HĐ %(n)s: khai TK cho dòng GỐC (tab Kế toán — TK '
                    'nợ gốc thuê TC hoặc TK phải thu thuê TC) trước khi '
                    'lên hóa đơn kỳ tài chính.', n=c.name))
            lines.append((0, 0, {
                'name': _('Gốc thuê TC — %(l)s', l=label),
                'quantity': 1.0,
                'price_unit': self.principal_amount,
                'account_id': principal_account.id,
                'tax_ids': [(6, 0, [])],  # gốc không chịu VAT
            }))
            interest_vals = {
                'name': _('Lãi thuê TC — %(l)s', l=label),
                'quantity': 1.0,
                'price_unit': self.interest_amount,
                'tax_ids': taxes,
            }
            if c.account_interest_id:
                interest_vals['account_id'] = c.account_interest_id.id
            lines.append((0, 0, interest_vals))
        else:
            rent_vals = {
                'name': _('Tiền thuê — %(l)s', l=label),
                'quantity': 1.0,
                'price_unit': self.rent_amount,
                'tax_ids': taxes,
            }
            if c.account_rent_id:
                rent_vals['account_id'] = c.account_rent_id.id
            lines.append((0, 0, rent_vals))
        return {
            'move_type': move_type,
            'partner_id': c.partner_id.id,
            'invoice_date': self.date_due,
            'invoice_date_due': self.date_due,
            'ref': label,
            'invoice_origin': c.name,
            'invoice_line_ids': lines,
        }

    def action_view_invoice(self):
        self.ensure_one()
        if not self.invoice_id:
            raise UserError(_('Kỳ này chưa có hóa đơn.'))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': self.invoice_id.id,
            'view_mode': 'form',
        }

    def action_register_payment(self):
        """Mở wizard thanh toán chuẩn của Odoo cho hóa đơn của kỳ này.

        Thanh toán xong → payment_state hóa đơn đổi → state kỳ tự thành
        'Đã thanh toán' (compute từ invoice)."""
        self.ensure_one()
        inv = self.invoice_id
        if not inv or inv.state == 'cancel':
            raise UserError(_(
                'Kỳ này chưa có hóa đơn — bấm "Tạo hóa đơn" trước.'))
        if inv.state != 'posted':
            raise UserError(_(
                'Hóa đơn của kỳ này chưa vào sổ — xác nhận (post) hóa '
                'đơn trước khi thanh toán.'))
        if inv.payment_state in ('paid', 'in_payment', 'reversed'):
            raise UserError(_('Kỳ này đã thanh toán.'))
        return {
            'name': _('Thanh toán kỳ %s') % (self.sequence or ''),
            'type': 'ir.actions.act_window',
            'res_model': 'account.payment.register',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'active_model': 'account.move',
                'active_ids': inv.ids,
            },
        }
