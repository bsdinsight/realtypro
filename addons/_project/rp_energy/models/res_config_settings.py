# -*- coding: utf-8 -*-
"""Cờ "chỉ dùng cho dự án năng lượng" — ẩn phần giao diện của nhà ở.

Cài rp_energy KHÔNG đủ để kết luận cả bản triển khai là năng lượng.
Bản demo công khai của Realty có cài rp_energy (nó có một dự án điện
gió mẫu) nhưng đồng thời vẫn giữ 338 căn hộ, 7 toà nhà, 124 sàn của
các dự án bất động sản — mà `rp_estimate.menu_pm_*` là lối vào DUY
NHẤT tới khối dữ liệu đó (bộ menu cùng tên của re_core không tồn tại).
Ẩn menu theo "đã cài module" là cắt mất lối vào đó.

Nên việc ẩn là lựa chọn của TỪNG bản triển khai, đặt ở Cấu hình. Mặc
định tắt: bản triển khai bất động sản không thấy gì khác.
"""
from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Chỉ có nghĩa khi dự án có căn hộ để bán.
    _RP_ENERGY_MENU_NHA_O = (
        'rp_estimate.menu_pm_subzones',
        'rp_estimate.menu_pm_buildings',
        'rp_estimate.menu_pm_floors',
        'rp_estimate.menu_pm_units',
        'rp_estimate.menu_pm_unit_types',
    )
    _RP_ENERGY_MENU_NANG_LUONG = (
        'rp_energy.menu_pm_phase',
    )

    rp_energy_only_ui = fields.Boolean(
        string='Chỉ dùng cho dự án năng lượng',
        config_parameter='rp_energy.only_ui',
        help='Trong Project Master: ẩn Subzones / Buildings / Floors / '
             'Units / Unit Types và thay bằng "Phase". Nhà máy điện '
             'chia dự án theo giai đoạn và không có căn hộ để bán, nên '
             'các mục đó mở ra lúc nào cũng rỗng.\n'
             'CHỈ bật trên bản triển khai không quản lý nhà ở — bật ở '
             'nơi có dữ liệu căn hộ là cắt mất lối vào duy nhất tới '
             'khối dữ liệu đó. Chỉ ẩn, không xoá: tắt cờ là menu hiện '
             'lại nguyên vẹn.')

    def set_values(self):
        res = super().set_values()
        self._rp_energy_ap_dung_ui(self.rp_energy_only_ui)
        return res

    @api.model
    def _rp_energy_co_bat_only_ui(self):
        """Đọc cờ ra kiểu bool. Tham số lưu dạng chuỗi nên 'False' mà
        đưa thẳng vào `bool()` sẽ ra True."""
        raw = self.env['ir.config_parameter'].sudo().get_param(
            'rp_energy.only_ui')
        return str(raw or '').strip().lower() in ('true', '1', 'yes')

    @api.model
    def _rp_energy_ap_dung_ui(self, chi_nang_luong):
        """Bật đúng một trong hai lối vào, tắt lối còn lại."""
        doi = [(x, not chi_nang_luong) for x in self._RP_ENERGY_MENU_NHA_O]
        doi += [(x, bool(chi_nang_luong))
                for x in self._RP_ENERGY_MENU_NANG_LUONG]
        for xmlid, bat in doi:
            menu = self.env.ref(xmlid, raise_if_not_found=False)
            if menu and menu.active != bat:
                menu.sudo().active = bat
        # Menu nằm trong cache theo nhóm người dùng; không dọn thì người
        # đang mở phiên vẫn thấy cây menu cũ cho tới khi hết phiên.
        self.env.registry.clear_cache()
