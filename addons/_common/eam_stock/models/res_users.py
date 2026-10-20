# -*- coding: utf-8 -*-
"""Phân quyền theo kho (KHO-40).

Cách làm: một nhóm quyền riêng **Chỉ thấy kho được giao**. Ai KHÔNG ở
trong nhóm đó thì không bị ảnh hưởng gì — quản trị, kế toán, ban giám đốc
vẫn thấy toàn bộ.

Làm ngược lại (mặc định ai cũng bị hạn chế, trừ khi khai kho) là cách
chắc chắn khoá nhầm chính mình ngay lần đầu bật tính năng, và lúc đó
không còn ai vào sửa được nữa.
"""
from markupsafe import Markup

from odoo import _, fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    eam_warehouse_ids = fields.Many2many(
        'stock.warehouse', 'eam_user_warehouse_rel', 'user_id', 'warehouse_id',
        string='Kho được giao',
        help='Chỉ có tác dụng khi người dùng thuộc nhóm "Chỉ thấy kho '
             'được giao". Bỏ trống mà vẫn ở trong nhóm đó thì không thấy '
             'kho nào — đó là có chủ đích, để quên khai là lộ ra ngay chứ '
             'không âm thầm cho xem hết.')

    def _eam_kho_duoc_phep(self):
        """Kho mà người này được thao tác. ``None`` nghĩa là không hạn chế."""
        self.ensure_one()
        if not self.has_group('eam_stock.group_eam_warehouse_limited'):
            return None
        return self.eam_warehouse_ids


    def write(self, vals):
        """Ghi vết đổi kho được giao — TỰ GHI, không dùng ``tracking=``.

        Odoo 19 **bỏ qua âm thầm** tham số ``tracking`` trên trường của
        model không kế thừa ``mail.thread``: chỉ có một dòng WARNING lúc
        nạp, còn chạy thì không lỗi gì, và cũng không có vết nào. Tưởng
        có nhật ký mà không có là tệ hơn biết mình không có.

        Quyền ra vào kho là thứ kiểm toán sẽ hỏi, nên ghi sang chatter
        của đối tác gắn với người dùng — nơi chắc chắn có mail.thread.
        """
        cu = {u.id: set(u.eam_warehouse_ids.ids) for u in self} \
            if 'eam_warehouse_ids' in vals else {}
        res = super().write(vals)
        for u in self.filtered(lambda x: x.id in cu):
            moi = set(u.eam_warehouse_ids.ids)
            if moi == cu[u.id]:
                continue
            W = self.env['stock.warehouse']
            them = W.browse(list(moi - cu[u.id])).mapped('name')
            bot = W.browse(list(cu[u.id] - moi)).mapped('name')
            phan = []
            if them:
                phan.append(_('thêm: %s', ', '.join(them)))
            if bot:
                phan.append(_('bỏ: %s', ', '.join(bot)))
            u.partner_id.message_post(body=Markup(
                _('<b>Đổi kho được giao</b> cho %(ng)s — %(pt)s.',
                  ng=u.name, pt='; '.join(phan))))
        return res
