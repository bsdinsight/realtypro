# -*- coding: utf-8 -*-
from . import models


def post_init_hook(env):
    """Đặt menu Project Master đúng theo cờ của bản triển khai.

    `<menuitem>` tạo menu "Phase" ở trạng thái bật. Bản triển khai bất
    động sản không khai cờ nên phải tắt nó ngay sau khi nạp dữ liệu,
    nếu không mỗi lần cài mới sẽ thấy cả "Subzones" lẫn "Phase".
    """
    env['res.config.settings']._rp_energy_ap_dung_ui(
        env['res.config.settings']._rp_energy_co_bat_only_ui())
