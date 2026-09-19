# -*- coding: utf-8 -*-
from odoo import api, models


class AccountAccount(models.Model):
    _inherit = 'account.account'

    # Odoo 19 chỉ ghép SỐ HIỆU vào tên tài khoản cho người có quyền xem
    # sổ kế toán (account.group_account_readonly). Người làm tín dụng
    # thường không có quyền đó, nên ô "TK kiểm soát dòng tiền" trên HĐTD
    # chỉ hiện tên — mà nhiều tài khoản trùng tên khác số hiệu (backlog
    # 1083). Ô nào cần thấy số hiệu thì bật context re_show_account_code;
    # các chỗ khác của Odoo giữ nguyên hành vi gốc.
    @api.depends_context('company', 'formatted_display_name',
                         're_show_account_code')
    @api.depends('code')
    def _compute_display_name(self):
        super()._compute_display_name()
        if not self.env.context.get('re_show_account_code'):
            return
        for account in self:
            shown = (account.display_name or '').lstrip()
            if account.code and not shown.startswith(account.code):
                account.display_name = '%s %s' % (account.code, shown)
