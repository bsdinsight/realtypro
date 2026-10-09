# -*- coding: utf-8 -*-
"""Ẩn ứng dụng "Mua hàng" gốc của Odoo sau MỖI lần nạp registry.

Vì sao phải ẩn
--------------
Hai ứng dụng cùng chạy trên một bảng ``purchase.order``, với bộ lọc khác
nhau. "Mua sắm" lọc đơn đã gắn dự án; "Mua hàng" gốc không lọc gì. Người
dùng tạo một đơn ở ứng dụng gốc mà quên gắn dự án thì đơn đó **biến mất
khỏi màn hình của mình** — tiền đã cam kết, không màn nào hiện. Giữ hai
đường vào song song là bảo đảm chuyện đó sẽ xảy ra.

Vì sao KHÔNG khai được bằng XML
-------------------------------
``<menuitem>`` ghi ``active`` **vô điều kiện**, mặc định True
(``odoo/tools/convert.py`` ``_tag_menuitem``, dòng khởi tạo ``values``).
Nên bất kỳ lượt ``-u purchase`` nào — kể cả khi nâng cấp vì việc hoàn
toàn khác — cũng bật lại ứng dụng đã tắt. Trình nạp ghi đè hết: parent,
name, sequence, action, group và cả active. Thứ duy nhất nó KHÔNG đụng
tới là dữ liệu bên ngoài XML, nên lời giải là kiểm lại và sửa sau khi
nạp xong.

Đây không phải giả thuyết: cùng cơ chế đã làm hỏng cờ giao diện bên
``rp_energy`` một lần, và chú thích ở đó ghi lại sự việc.

Tắt được
--------
Tham số hệ thống ``rp_purchase.hide_native_purchase``. Đặt ``0`` thì
ứng dụng gốc hiện lại — dành cho khách muốn dùng luồng mua hàng chuẩn
của Odoo song song.
"""
import logging

from odoo import models

_logger = logging.getLogger(__name__)

THAM_SO = 'rp_purchase.hide_native_purchase'


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    def _register_hook(self):
        res = super()._register_hook()
        try:
            self.sudo()._rp_ap_dung_an_mua_hang()
        except Exception:
            # Một lỗi ở đây mà ném ra sẽ chặn luôn việc nạp cả cơ sở dữ
            # liệu — cái giá đắt hơn nhiều so với việc menu hiện sai.
            _logger.exception(
                'rp_purchase: không áp lại được cờ ẩn ứng dụng Mua hàng '
                'gốc; có thể đang có hai đường vào đơn mua.')
        return res

    def _rp_ap_dung_an_mua_hang(self):
        goc = self.env.ref('purchase.menu_purchase_root',
                           raise_if_not_found=False)
        if not goc:
            return
        tham = self.env['ir.config_parameter'].sudo().get_param(THAM_SO, '1')
        nen_an = tham not in ('0', 'False', 'false', '')
        # Chỉ GHI khi trạng thái sai. Bình thường hàm này chỉ đọc một bản
        # ghi rồi thôi, không làm chậm mỗi lượt khởi động.
        if goc.active == nen_an:
            goc.write({'active': not nen_an})
            _logger.info(
                'rp_purchase: %s ứng dụng "Mua hàng" gốc của Odoo.',
                'đã ẩn' if nen_an else 'đã hiện lại')
