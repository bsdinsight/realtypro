# -*- coding: utf-8 -*-
from email.message import EmailMessage

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestDemoGuard(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Param = cls.env['ir.config_parameter'].sudo()
        cls.demo = cls.env['res.users'].create({
            'name': 'Demo guard',
            'login': 'demo_guard_test',
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id])],
        })
        cls.other = cls.env['res.users'].create({
            'name': 'Người khác',
            'login': 'demo_guard_other',
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id])],
        })

    def _lock(self, logins='demo_guard_test'):
        self.Param.set_param('bsd_demo_guard.locked_logins', logins)

    def _as_self(self, user):
        """Đúng luồng thật của Odoo 19: wizard "Đổi mật khẩu" gọi
        ``self.env.user._change_password(...)`` — ``env.user`` mang quyền
        sudo nhưng GIỮ uid của người dùng. Gọi bằng ``with_user`` trơn
        (không sudo) thì vấp quyền ghi res.users trước khi tới phép chặn,
        và test đo nhầm chỗ."""
        return self.env(user=user).user

    # ------------------------------------------------------------------
    def test_no_param_changes_nothing(self):
        """Chưa khai tham số thì module vô hại."""
        self._as_self(self.demo)._change_password('mat-khau-moi')

    def test_locked_user_cannot_change_own_password(self):
        self._lock()
        with self.assertRaises(UserError):
            self._as_self(self.demo)._change_password('mat-khau-moi')

    def test_admin_can_still_reset_locked_user(self):
        """Team phải còn đường sửa tài khoản demo mà không gỡ module."""
        self._lock()
        self.demo.with_user(self.env.ref('base.user_admin'))._change_password(
            'demo')

    def test_other_users_unaffected(self):
        self._lock()
        self._as_self(self.other)._change_password('mat-khau-moi')

    def test_locked_user_cannot_enable_totp(self):
        self._lock()
        with self.assertRaises(UserError):
            self.demo.with_user(self.demo).action_totp_enable_wizard()

    def test_list_of_logins(self):
        self._lock(' demo_guard_other , demo_guard_test ')
        with self.assertRaises(UserError):
            self._as_self(self.demo)._change_password('x')
        with self.assertRaises(UserError):
            self._as_self(self.other)._change_password('x')

    # ------------------------------------------------------------------
    def _message(self):
        msg = EmailMessage()
        msg['Subject'] = 'Báo giá'
        msg['From'] = 'demo@example.test'
        msg['To'] = 'khach@example.test'
        msg['Message-Id'] = '<test-guard@example.test>'
        msg.set_content('x')
        return msg

    def test_mail_blocked_returns_message_id(self):
        self.Param.set_param('bsd_demo_guard.block_outgoing_mail', '1')
        res = self.env['ir.mail_server'].send_email(self._message())
        self.assertEqual(res, '<test-guard@example.test>')
