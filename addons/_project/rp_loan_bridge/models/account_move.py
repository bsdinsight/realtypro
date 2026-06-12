# -*- coding: utf-8 -*-
"""Inherit account.move: auto-fill bank account của nhà cung cấp."""
from odoo import api, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    @api.onchange('partner_id')
    def _onchange_partner_id_set_bank(self):
        """Khi pick nhà cung cấp, auto-fill TK nhận tiền (partner_bank_id):

        - Nếu nhà cung cấp có đúng 1 TK NH → set sẵn
        - Nếu >1 TK → giữ rỗng (user pick từ dropdown chuẩn Odoo)
        - Nếu 0 TK → giữ rỗng (user có thể tạo mới qua widget M2O)

        Chỉ áp dụng cho vendor bill (in_invoice, in_refund). Customer
        invoice không cần TK NH bên đối tác.
        """
        if self.move_type not in ('in_invoice', 'in_refund'):
            return
        if not self.partner_id:
            self.partner_bank_id = False
            return
        accounts = self.partner_id.bank_ids
        if len(accounts) == 1:
            self.partner_bank_id = accounts
