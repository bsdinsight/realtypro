# -*- coding: utf-8 -*-
"""Áp lại cờ "chỉ dùng cho dự án năng lượng" sau MỖI lần nạp registry.

Vì sao cần: `<menuitem>` ghi trường `active` VÔ ĐIỀU KIỆN, mặc định True
(`odoo/tools/convert.py` `_tag_menuitem`). Nên bất kỳ lượt `-u
rp_estimate` nào — kể cả khi người ta nâng cấp vì việc hoàn toàn khác —
cũng bật lại năm menu bất động sản mà bản triển khai năng lượng đã tắt.
Đây không phải giả thuyết: đã xảy ra thật, lúc nâng cấp rp_estimate để
gom menu Ngân sách.

Không có cách nào khai trong XML để chống lại việc đó, vì trình nạp ghi
đè hết: parent, name, sequence, action, group và cả active. Thứ duy nhất
trình nạp KHÔNG đụng tới là dữ liệu bên ngoài XML — nên lời giải là
kiểm lại và sửa sau khi nạp xong.

`_register_hook` chạy mỗi lần registry được dựng, tức sau mỗi lượt `-u`
và mỗi lần khởi động. Bình thường nó chỉ đọc sáu bản ghi rồi thôi; chỉ
ghi khi trạng thái sai. Bọc try/except vì một lỗi ở đây mà ném ra sẽ
chặn luôn việc nạp cả cơ sở dữ liệu — cái giá đắt hơn nhiều so với việc
menu hiện sai.
"""
import logging

from odoo import models

_logger = logging.getLogger(__name__)


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    def _register_hook(self):
        res = super()._register_hook()
        try:
            CS = self.env['res.config.settings'].sudo()
            CS._rp_energy_ap_dung_ui(CS._rp_energy_co_bat_only_ui())
        except Exception:
            _logger.exception(
                'rp_energy: không áp lại được cờ giao diện năng lượng; '
                'menu bất động sản có thể đang hiện sai.')
        return res
