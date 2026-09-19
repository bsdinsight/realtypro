# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged('post_install', '-at_install', 're_loan_borrowing_base')
class TestControlledAccountDisplay(TransactionCase):
    """Backlog 1083: ô TK kiểm soát dòng tiền phải hiện cả số hiệu tài
    khoản, kể cả với người KHÔNG có quyền xem sổ kế toán."""

    def test_code_shown_only_where_asked(self):
        account = self.env['account.account'].create({
            'code': '112199', 'name': 'TK kiểm soát NH thử',
            'account_type': 'asset_cash'})
        user = new_test_user(self.env, login='loan_no_acc',
                             groups='base.group_user')
        self.assertFalse(user.has_group('account.group_account_readonly'))
        # sudo() giữ nguyên người dùng (has_group vẫn xét user thử),
        # chỉ bỏ qua quyền đọc bảng tài khoản — thứ không phải đối
        # tượng của phép thử này.
        acc = account.with_user(user).sudo()
        self.assertEqual(acc.display_name, 'TK kiểm soát NH thử')
        self.assertEqual(
            acc.with_context(re_show_account_code=True).display_name,
            '112199 TK kiểm soát NH thử')
