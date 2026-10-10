# -*- coding: utf-8 -*-
from odoo import models


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    def _load_menus_blacklist(self):
        """Ẩn menu "Mô phỏng giao dịch (demo)" ngoài DB demo.

        Nhóm quyền đã chặn người thường; lớp này để admin của DB khách thật
        không thấy một nút bơm tiền giả nằm cạnh giao dịch thật.
        """
        res = super()._load_menus_blacklist()
        if not self.env['re.bank.sepay.simulate.wizard']._simulation_enabled():
            menu = self.env.ref('re_bank_sync.menu_sepay_simulate',
                                raise_if_not_found=False)
            if menu:
                res.append(menu.id)
        return res
