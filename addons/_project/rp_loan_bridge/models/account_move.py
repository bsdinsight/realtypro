# -*- coding: utf-8 -*-
"""Inherit account.move: auto-fill bank account của nhà cung cấp."""
from odoo import api, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    @api.onchange('partner_id')
    def _onchange_partner_id_set_bank(self):
        """Khi pick nhà cung cấp, auto-fill TK nhận tiền:

        - Có >=1 TK NH → set sẵn TK đầu tiên (user vẫn đổi được qua
          dropdown nếu có nhiều TK)
        - 0 TK → giữ rỗng, user click vào field 'Ngân hàng người nhận'
          → 'Tạo và sửa' để mở form res.partner.bank với
          default_partner_id đã set sẵn

        Chỉ áp dụng cho vendor bill (in_invoice, in_refund). Customer
        invoice không cần TK NH bên đối tác.
        """
        if self.move_type not in ('in_invoice', 'in_refund'):
            return
        if not self.partner_id:
            self.partner_bank_id = False
            return
        accounts = self.partner_id.bank_ids
        if accounts:
            # Pick first — chuẩn Odoo sort theo sequence, default thường
            # là TK chính.
            self.partner_bank_id = accounts[:1]
        else:
            self.partner_bank_id = False
