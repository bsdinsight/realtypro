# -*- coding: utf-8 -*-
"""Tài khoản kế toán cho Tạm ứng (backlog 969).

Team khách hàng chốt 2026-09-11: tạm ứng sinh THẲNG phiếu chi, không
qua hoá đơn, đối ứng TK 331 — "trả trước người bán". Nhờ vậy khi hoá
đơn nhà thầu về, phiếu chi tạm ứng cấn trừ thẳng vào hoá đơn bằng cơ
chế đối trừ sẵn có của Odoo, không phải khai tay.

Tài khoản phải là loại CÔNG NỢ PHẢI TRẢ thì mới đối trừ được với hoá
đơn nhà cung cấp — khai nhầm sang tài khoản chi phí thì tiền tạm ứng
thành chi phí ngay lúc chuyển, và không bao giờ cấn trừ được.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    rp_advance_journal_id = fields.Many2one(
        'account.journal', string='Sổ nhật ký chi (Tạm ứng)',
        domain="[('type', 'in', ('bank', 'cash'))]",
        config_parameter='rp_advance_payment.journal_id',
        help='Sổ nhật ký mặc định khi ghi nhận thanh toán tạm ứng. '
             'Vẫn đổi được ở từng lần ghi nhận.')
    rp_advance_account_id = fields.Many2one(
        'account.account', string='TK trả trước người bán (Tạm ứng)',
        domain="[('account_type', '=', 'liability_payable')]",
        config_parameter='rp_advance_payment.account_id',
        help='Đối ứng phiếu chi tạm ứng (331). Phải là tài khoản công '
             'nợ phải trả thì phiếu chi mới cấn trừ được vào hoá đơn '
             'nhà thầu sau này.')

    @api.model
    def _advance_payment_account(self):
        raw = self.env['ir.config_parameter'].sudo().get_param(
            'rp_advance_payment.account_id')
        try:
            account = self.env['account.account'].browse(int(raw or 0))
        except (TypeError, ValueError):
            return self.env['account.account']
        return account.exists()

    @api.model
    def _advance_payment_journal(self):
        raw = self.env['ir.config_parameter'].sudo().get_param(
            'rp_advance_payment.journal_id')
        try:
            journal = self.env['account.journal'].browse(int(raw or 0))
        except (TypeError, ValueError):
            journal = self.env['account.journal']
        journal = journal.exists()
        if journal:
            return journal
        return self.env['account.journal'].search(
            [('type', '=', 'bank'),
             ('company_id', '=', self.env.company.id)], limit=1)

    @api.model
    def _require_advance_account(self):
        account = self._advance_payment_account()
        if not account:
            raise UserError(_(
                "Chưa khai \"TK trả trước người bán (Tạm ứng)\".\n"
                "Vào Vay > Cấu hình > Tham số phân hệ Vay, mục \"Kế "
                "toán Tạm ứng\" để khai (thường là 331) — không có tài "
                "khoản thì phiếu chi hạch toán vào đâu cũng sai, và "
                "sau này không cấn trừ được vào hoá đơn."))
        return account
