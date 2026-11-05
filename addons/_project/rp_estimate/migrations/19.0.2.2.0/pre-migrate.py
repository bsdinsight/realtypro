# -*- coding: utf-8 -*-
"""Chuyển menu "Nhà cung cấp" từ rp_contractor sang rp_estimate.

Menu này từng khai ở rp_contractor với cha là
``rp_estimate.menu_rp_configuration``. Mà rp_estimate phụ thuộc
rp_contractor, nên trên cơ sở dữ liệu MỚI rp_contractor nạp trước, cha
chưa có → cài gãy ("External ID not found"). Giờ menu khai ở
rp_estimate (views/menus.xml) với cùng tên ``menu_cfg_supplier``.

Cơ sở dữ liệu đang chạy đã có bản ghi menu gắn xmlid
``rp_contractor.menu_cfg_supplier``. Không xử lý thì:

- ``-u rp_estimate`` (không nâng rp_contractor): xmlid cũ còn nguyên,
  rp_estimate tạo thêm menu mới → HAI menu "Nhà cung cấp".
- ``-u rp_contractor``: Odoo xoá menu cũ rồi tạo menu mới — vẫn một
  menu nhưng đổi id bản ghi, hai đường nâng cấp ra hai kết quả khác nhau.

Nên ĐỔI CHỦ xmlid ngay trước khi rp_estimate nạp dữ liệu: cùng bản ghi
menu, giờ thuộc rp_estimate; lượt nạp menus.xml chỉ cập nhật nó. Bước
dọn cuối lượt nâng cấp không đụng tới vì xmlid đã thuộc rp_estimate.

Chạy lại an toàn: không còn xmlid cũ thì không làm gì. Nếu xmlid mới
đã có sẵn (đã chạy dở), xoá bản ghi cũ thay vì đổi chủ để không trùng.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    cr.execute(
        """
        SELECT id, res_id FROM ir_model_data
         WHERE module = 'rp_contractor' AND name = 'menu_cfg_supplier'
           AND model = 'ir.ui.menu'
        """
    )
    old = cr.fetchone()
    if not old:
        return
    old_imd_id, old_menu_id = old

    cr.execute(
        """
        SELECT res_id FROM ir_model_data
         WHERE module = 'rp_estimate' AND name = 'menu_cfg_supplier'
        """
    )
    new = cr.fetchone()
    if new:
        cr.execute("DELETE FROM ir_model_data WHERE id = %s", (old_imd_id,))
        if new[0] != old_menu_id:
            cr.execute("DELETE FROM ir_ui_menu WHERE id = %s", (old_menu_id,))
        _logger.info(
            "rp_estimate: rp_estimate.menu_cfg_supplier đã có — xoá bản "
            "trùng rp_contractor.menu_cfg_supplier (menu id %s)",
            old_menu_id,
        )
        return

    cr.execute(
        "UPDATE ir_model_data SET module = 'rp_estimate' WHERE id = %s",
        (old_imd_id,),
    )
    _logger.info(
        "rp_estimate: chuyển xmlid rp_contractor.menu_cfg_supplier → "
        "rp_estimate.menu_cfg_supplier (menu id %s)",
        old_menu_id,
    )
