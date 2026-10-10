# -*- coding: utf-8 -*-
"""Mô phỏng giao dịch = bơm tiền giả vào đối soát → phải khoá chặt.

Lỗ hổng được vá: wizard cấp full quyền cho base.group_user và gọi
`ingest()` bằng sudo với nguồn 'sepay' → user nội bộ nào cũng tạo được
giao dịch tiền vào giả, tự khớp IPC, định giá lại TSBĐ.
"""
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, new_test_user, tagged

from odoo.addons.re_bank_sync.wizards.sepay_simulate import DEMO_PARAM


@tagged('post_install', '-at_install', 're_bank_sync')
class TestSimulateAccess(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Wizard = cls.env['re.bank.sepay.simulate.wizard']
        cls.Txn = cls.env['re.bank.transaction']
        cls.user = new_test_user(cls.env, login='bs_plain_user',
                                 groups='base.group_user')
        cls.integration_admin = new_test_user(
            cls.env, login='bs_integration_admin',
            groups='base.group_user,'
                   're_integration_hub.group_integration_admin')
        cls.env['ir.config_parameter'].sudo().set_param(DEMO_PARAM, '1')

    def _vals(self, content='chuyen tien demo'):
        return {'direction': 'in', 'amount': 1_000_000.0,
                'content': content}

    # ------------------------------------------------------------------
    def test_user_thuong_khong_mo_duoc_wizard(self):
        wiz = self.Wizard.with_user(self.user)
        self.assertFalse(self.user.share)
        self.assertFalse(wiz.env.su)
        self.assertEqual(wiz.env.uid, self.user.id)
        self.assertFalse(wiz.has_access('create'),
                         'User nội bộ thường không được có quyền wizard')
        with self.assertRaises(AccessError):
            wiz.create(self._vals())
        menu = self.env.ref('re_bank_sync.menu_sepay_simulate')
        self.assertNotIn(
            menu.id, self.env['ir.ui.menu'].with_user(
                self.user)._visible_menu_ids(),
            'User thường không được thấy menu mô phỏng')

    def test_user_thuong_khong_goi_duoc_action_du_co_ban_ghi(self):
        """Phòng lớp 2: có sẵn bản ghi wizard (vd tạo bằng sudo) thì user
        thường gọi action vẫn bị chặn trước khi tới ingest sudo."""
        wiz = self.Wizard.create(self._vals('IPC-PROBE'))
        before = self.Txn.search_count([])
        with self.assertRaises(AccessError):
            wiz.with_user(self.user).action_simulate()
        self.assertEqual(self.Txn.search_count([]), before)

    def test_integration_admin_mo_phong_voi_nguon_rieng(self):
        wiz = self.Wizard.with_user(self.integration_admin).create(
            self._vals())
        res = wiz.action_simulate()
        txn = self.Txn.browse(res['res_id'])
        self.assertEqual(txn.source, 'demo_simulate',
                         'Giao dịch giả không được mang nguồn sepay')
        self.assertTrue(txn.external_id.startswith('SIM'))

    def test_db_that_khong_mo_phong_va_an_menu(self):
        menu = self.env.ref('re_bank_sync.menu_sepay_simulate')
        Menu = self.env['ir.ui.menu']
        self.assertNotIn(menu.id, Menu._load_menus_blacklist())

        self.env['ir.config_parameter'].sudo().set_param(DEMO_PARAM, '0')
        self.assertIn(menu.id, Menu._load_menus_blacklist(),
                      'Ngoài DB demo menu mô phỏng phải bị ẩn')
        wiz = self.Wizard.with_user(self.integration_admin).create(
            self._vals())
        with self.assertRaises(UserError):
            wiz.action_simulate()
