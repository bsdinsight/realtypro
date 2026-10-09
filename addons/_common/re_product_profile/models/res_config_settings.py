# -*- coding: utf-8 -*-
from odoo import _, api, fields, models

from .ir_ui_menu import (KHONG_BAO_GIO_AN, MENU_AN_THEO_HO_SO,
                         THAM_SO_AN_THEM, THAM_SO_HO_SO)

HO_SO = [
    ('full', 'Đầy đủ — không ẩn menu nào'),
    ('epc', 'EPC — Xây dựng & Năng lượng'),
    ('realty', 'Bất động sản — CRM / Bán hàng / Vận hành'),
]


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    rp_product_profile = fields.Selection(
        HO_SO, string='Hồ sơ sản phẩm', default='full',
        config_parameter=THAM_SO_HO_SO,
        help='Quyết định những menu gốc nào KHÔNG hiện cho bản triển '
             'khai này. Chỉ ẩn trên giao diện — không gỡ module, không '
             'xoá dữ liệu, và đổi lại là hiện ngay.')
    rp_profile_extra_hidden = fields.Char(
        string='Ẩn thêm (xmlid, cách nhau bởi dấu phẩy)',
        config_parameter=THAM_SO_AN_THEM,
        help='Dành cho vài menu lẻ muốn tỉa ngoài hồ sơ. Ví dụ: '
             'utm.menu_link_tracker_root. Bỏ trống nếu không cần.')
    rp_profile_preview = fields.Text(
        string='Sẽ ẩn những menu này', compute='_compute_profile_preview',
        help='Liệt kê ngay tại đây để việc ẩn menu không thành một hộp '
             'đen: nhìn là biết mình vừa chọn cái gì.')

    @api.depends('rp_product_profile', 'rp_profile_extra_hidden')
    def _compute_profile_preview(self):
        Menu = self.env['ir.ui.menu']
        for s in self:
            xmlids = list(MENU_AN_THEO_HO_SO.get(
                s.rp_product_profile or 'full', ()))
            them = (s.rp_profile_extra_hidden or '').replace('\n', ',')
            xmlids += [x.strip() for x in them.split(',')]
            dong = []
            for xmlid in xmlids:
                if not xmlid:
                    continue
                if xmlid in KHONG_BAO_GIO_AN:
                    dong.append(_('· %s — BỎ QUA: ẩn menu này thì không '
                                  'còn đường quay lại để đổi hồ sơ.',
                                  xmlid))
                    continue
                m = self.env.ref(xmlid, raise_if_not_found=False)
                if m is None or m._name != 'ir.ui.menu':
                    dong.append(_('· %s — không có trên bản này, bỏ qua.',
                                  xmlid))
                else:
                    con = Menu.search_count([('parent_id', 'child_of', m.id)])
                    dong.append(_('· %(ten)s  (%(x)s) — kèm %(n)s mục con',
                                  ten=m.name, x=xmlid, n=con))
            s.rp_profile_preview = '\n'.join(dong) or _(
                'Không ẩn menu nào — mọi dòng sản phẩm đều hiện.')

    def set_values(self):
        """Lưu xong phải XOÁ CACHE, nếu không đổi hồ sơ mà menu đứng im.

        ``load_menus`` và ``load_menus_root`` đều bọc ``ormcache`` theo
        người dùng. Odoo chỉ tự xoá cache đó khi bản ghi ``ir.ui.menu``
        bị ghi — mà ở đây ta không đụng tới menu nào, chỉ đổi một tham
        số. Thiếu dòng này thì người dùng bấm Lưu, không thấy gì đổi, và
        kết luận là tính năng hỏng.
        """
        res = super().set_values()
        self.env.registry.clear_cache()
        return res
