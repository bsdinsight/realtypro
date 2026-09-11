# -*- coding: utf-8 -*-
"""Ghi nhận một đợt thanh toán tạm ứng bằng tiền công ty (backlog 969).

Trước đây tạm ứng chỉ có MỘT nút "Đánh dấu Đã thanh toán" — bấm một
cái là xong cả phiếu, không chia được nhiều đợt, và không sinh chứng
từ kế toán nào. Team khách hàng yêu cầu trả nhiều đợt và mỗi đợt là
một phiếu chi thật.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class RpAdvanceRegisterPayment(models.TransientModel):
    _name = 'rp.advance.register.payment'
    _description = 'Ghi nhận thanh toán Tạm ứng'

    advance_id = fields.Many2one(
        'rp.advance.payment', string='Phiếu tạm ứng', required=True,
        readonly=True)
    partner_id = fields.Many2one(
        related='advance_id.partner_id', string='Nhà thầu / NCC',
        readonly=True)
    currency_id = fields.Many2one(
        related='advance_id.currency_id', readonly=True)
    amount_total = fields.Monetary(
        related='advance_id.amount', string='Giá trị tạm ứng',
        readonly=True)
    amount_unpaid = fields.Monetary(
        related='advance_id.amount_unpaid', string='Còn phải trả',
        readonly=True)
    amount = fields.Monetary(
        string='Số tiền đợt này', required=True,
        help='Mặc định là phần còn phải trả. Sửa xuống nếu trả nhiều '
             'đợt.')
    date = fields.Date(
        string='Ngày chi', required=True,
        default=fields.Date.context_today)
    journal_id = fields.Many2one(
        'account.journal', string='Sổ nhật ký', required=True,
        domain="[('type', 'in', ('bank', 'cash'))]")
    memo = fields.Char(string='Diễn giải')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        advance = self.env['rp.advance.payment'].browse(
            self.env.context.get('active_id'))
        if advance.exists():
            res.setdefault('advance_id', advance.id)
            res.setdefault('amount', advance.amount_unpaid)
            res.setdefault('memo', _("Tạm ứng %s", advance.name or ''))
        journal = self.env['res.config.settings'].sudo(
        )._advance_payment_journal()
        if journal:
            res.setdefault('journal_id', journal.id)
        return res

    @api.constrains('amount')
    def _check_amount(self):
        for wiz in self:
            if wiz.amount <= 0:
                raise ValidationError(_("Số tiền phải lớn hơn 0."))
            # Chặn trả vượt: tạm ứng trả dư thì phần dư không có gì
            # cấn trừ, treo lại ở 331 mà không ai biết vì sao.
            if wiz.amount > wiz.advance_id.amount_unpaid + 0.01:
                raise ValidationError(_(
                    "Số tiền %(a)s ₫ vượt phần còn phải trả của tạm "
                    "ứng (%(r)s ₫).",
                    a='{:,.0f}'.format(wiz.amount),
                    r='{:,.0f}'.format(wiz.advance_id.amount_unpaid)))

    def action_confirm(self):
        self.ensure_one()
        advance = self.advance_id
        if advance.state not in ('approved', 'partial_paid'):
            raise UserError(_(
                "Chỉ ghi nhận thanh toán cho tạm ứng Đã duyệt hoặc "
                "đang Thanh toán một phần. Hiện: %s.",
                dict(advance._fields['state'].selection).get(
                    advance.state)))
        if not advance.partner_id:
            raise UserError(_(
                "Tạm ứng chưa khai Nhà thầu / NCC — không biết chi "
                "cho ai."))
        account = self.env['res.config.settings'].sudo(
        )._require_advance_account()
        payment = self.env['account.payment'].create({
            'payment_type': 'outbound',
            'partner_type': 'supplier',
            'partner_id': advance.partner_id.id,
            'amount': self.amount,
            'date': self.date,
            'journal_id': self.journal_id.id,
            'destination_account_id': account.id,
            'memo': self.memo or advance.name,
            'advance_payment_id': advance.id,
        })
        payment.action_post()
        advance.invalidate_recordset(
            ['amount_paid', 'amount_paid_direct', 'amount_unpaid'])
        advance.message_post(body=_(
            "Ghi nhận thanh toán %(a)s ₫ bằng tiền công ty — phiếu chi "
            "%(p)s. Đã trả %(paid)s/%(tot)s ₫.",
            a='{:,.0f}'.format(self.amount), p=payment.name,
            paid='{:,.0f}'.format(advance.amount_paid),
            tot='{:,.0f}'.format(advance.amount)))
        # Đẩy trạng thái theo tiền đã trả (approved -> một phần -> đủ).
        advance._update_paid_state()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Phiếu chi'),
            'res_model': 'account.payment',
            'res_id': payment.id,
            'view_mode': 'form',
        }
