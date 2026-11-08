# -*- coding: utf-8 -*-
"""Khoá tài khoản dùng chung của bản demo công khai.

CHẶN Ở ``_change_password``, KHÔNG CHẶN Ở NÚT. Mọi lối đổi mật khẩu của
Odoo 19 đều đổ về hàm này: hộp "Đổi mật khẩu" trong Tuỳ chọn
(``change_password`` → ``_change_password``), wizard quản trị đổi hộ,
và cả lời gọi RPC thẳng. Chặn ở nút thì một lời gọi ``call_kw`` là
vượt qua.

CHỈ CHẶN KHI CHÍNH NGƯỜI ĐÓ ĐỔI. Quản trị viên (hoặc odoo shell) đổi hộ
vẫn được — lỡ ai đó tìm ra cách khác làm hỏng tài khoản demo thì team
còn đường sửa mà không phải gỡ module.
"""
from odoo import _, models
from odoo.exceptions import UserError

PARAM_LOCKED = 'bsd_demo_guard.locked_logins'


class ResUsers(models.Model):
    _inherit = 'res.users'

    def _bsd_demo_locked_logins(self):
        raw = self.env['ir.config_parameter'].sudo().get_param(
            PARAM_LOCKED) or ''
        return {x.strip() for x in raw.split(',') if x.strip()}

    def _bsd_demo_is_locked_self(self):
        """True khi bản ghi này là tài khoản bị khoá VÀ đang tự sửa mình."""
        self.ensure_one()
        return (self.login in self._bsd_demo_locked_logins()
                and self.env.uid == self.id)

    def _change_password(self, new_passwd):
        for user in self:
            if user._bsd_demo_is_locked_self():
                raise UserError(_(
                    'Đây là tài khoản demo dùng chung nên không đổi được '
                    'mật khẩu — đổi đi thì người xem sau không vào được '
                    'nữa.'))
        return super()._change_password(new_passwd)

    def action_totp_enable_wizard(self):
        # Bật 2FA trên tài khoản dùng chung là khoá ngoài mọi người còn
        # lại, và chỉ người giữ điện thoại tạo mã mới gỡ được.
        for user in self:
            if user._bsd_demo_is_locked_self():
                raise UserError(_(
                    'Đây là tài khoản demo dùng chung nên không bật được '
                    'xác thực hai lớp.'))
        return super().action_totp_enable_wizard()
