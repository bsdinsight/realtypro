# -*- coding: utf-8 -*-
"""Ẩn menu gốc của những dòng sản phẩm mà bản triển khai này không dùng.

Vì sao không dùng cờ ``active``
-------------------------------
Cách nhanh nhất để giấu một menu là đặt ``active = False`` trên chính bản
ghi menu. Làm vậy một lần thì được, nhưng với nhiều bản triển khai thì nó
hỏng ở ba chỗ:

* **Không ai biết vì sao.** Vài tháng sau mở DB ra thấy thiếu menu, không
  có chỗ nào nói đó là cố ý hay là sự cố.
* **Không lặp lại được.** Mỗi tenant mới lại phải nhớ sửa tay đúng những
  bản ghi ấy.
* **Trộn trạng thái với cấu hình.** ``active`` là dữ liệu; "khách này
  không dùng dòng bất động sản" là một *quyết định triển khai*.

Nên ở đây chỉ lưu MỘT tham số — hồ sơ sản phẩm — còn menu thì lọc lúc
dựng. Menu không bị đụng tới, đổi hồ sơ là hiện lại ngay.

Chặn ở HAI chỗ, không phải một
------------------------------
``load_menus`` có lọc theo ``_load_menus_blacklist``, và chặn menu GỐC là
đủ cho cả cây: hàm ``_set_app_id`` chỉ đi xuống từ các gốc còn lại, nên
menu con của một gốc bị chặn sẽ không có "app id" và bị loại ở bước sau.

Nhưng ``load_menus_root`` — thứ dựng danh sách ứng dụng — gọi thẳng
``get_user_roots`` và **không đi qua blacklist**. Chỉ chặn một chỗ thì
menu biến mất ở thanh trên mà vẫn còn trong danh sách ứng dụng.
"""
from odoo import api, models

# Hồ sơ → các menu GỐC bị ẩn. Khai bằng xmlid chuỗi và tra lúc chạy, nên
# module này KHÔNG phải phụ thuộc vào module khai menu: tenant nào không
# cài thì dòng đó lặng lẽ bỏ qua.
MENU_AN_THEO_HO_SO = {
    'full': (),
    'epc': (
        # Bất động sản: toà nhà, tầng, căn hộ, loại căn. Nhà máy điện
        # gió không có căn hộ nào.
        're_core.menu_re_core_root',
        # Phễu bán hàng. Chủ đầu tư EPC không bán gì qua CRM.
        'crm.crm_menu_root',
        # Đếm lượt bấm link chiến dịch. KHÔNG ẩn ở hồ sơ bất động sản —
        # bên đó có làm marketing nên vẫn dùng tới.
        'utm.menu_link_tracker_root',
    ),
    'realty': (
        'rp_estimate.menu_realty_project_root',
        'eam_core.menu_eam_root',
    ),
}

# Ẩn hai menu này thì không còn đường nào quay lại để đổi hồ sơ. Giữ
# tường minh một danh sách cấm, đừng trông vào việc người khai cẩn thận.
KHONG_BAO_GIO_AN = frozenset((
    'base.menu_administration',
    'base.menu_management',
))

THAM_SO_HO_SO = 'realtypro.product_profile'
THAM_SO_AN_THEM = 'realtypro.product_profile_extra_hidden'


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    @api.model
    def _rp_ho_so_hien_tai(self):
        return self.env['ir.config_parameter'].sudo().get_param(
            THAM_SO_HO_SO, 'full') or 'full'

    @api.model
    def _rp_menu_bi_an(self):
        """Id các menu gốc bị ẩn theo hồ sơ đang đặt."""
        P = self.env['ir.config_parameter'].sudo()
        xmlids = list(MENU_AN_THEO_HO_SO.get(self._rp_ho_so_hien_tai(), ()))
        # Ẩn thêm ngoài hồ sơ — để một bản triển khai tỉa vài menu lẻ mà
        # không phải sửa mã.
        them = P.get_param(THAM_SO_AN_THEM, '') or ''
        xmlids += [x.strip() for x in them.replace('\n', ',').split(',')]

        ids = []
        for xmlid in xmlids:
            if not xmlid or xmlid in KHONG_BAO_GIO_AN:
                continue
            menu = self.env.ref(xmlid, raise_if_not_found=False)
            if menu and menu._name == 'ir.ui.menu':
                ids.append(menu.id)
        return ids

    def _load_menus_blacklist(self):
        return super()._load_menus_blacklist() + self._rp_menu_bi_an()

    @api.model
    def get_user_roots(self):
        # load_menus_root KHÔNG lọc theo blacklist — xem chú thích đầu tệp.
        an = set(self._rp_menu_bi_an())
        return super().get_user_roots().filtered(lambda m: m.id not in an)
