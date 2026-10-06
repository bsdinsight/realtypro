# -*- coding: utf-8 -*-
"""Hai cờ giao diện của bản triển khai, hai chuyện khác nhau.

Cài rp_energy KHÔNG đủ để kết luận gì về cả bản triển khai. Bản demo
công khai của Realty có cài rp_energy (nó có một dự án điện gió mẫu)
nhưng đồng thời vẫn giữ 338 căn hộ, 7 toà nhà, 124 sàn của các dự án
bất động sản — mà `rp_estimate.menu_pm_*` là lối vào DUY NHẤT tới khối
dữ liệu đó. Ẩn menu theo "đã cài module" là cắt mất lối vào đó.

Nên việc ẩn là lựa chọn của TỪNG bản triển khai, đặt ở Cấu hình, mặc
định tắt cả hai.

**Hai cờ tách riêng vì chúng độc lập nhau:**

* *Ngành* — dự án năng lượng không có căn hộ để bán, nên bỏ nhánh nhà ở
  trong Project Master;
* *Vai* — nhánh "Doanh thu" dựng cho vai TỔNG THẦU: bán cho chủ đầu tư,
  phát hoá đơn về chủ đầu tư, chủ đầu tư trả tiền. Chủ đầu tư thì không
  có nghiệp vụ đó — doanh thu của họ đến từ việc khai thác công trình
  (nhà máy điện bán điện theo PPA), hoàn toàn khác.

Bốn tổ hợp đều có thật: chủ đầu tư điện gió (AMI, bật cả hai), nhà thầu
EPC điện gió (bật cờ ngành, TẮT cờ vai vì họ cần Doanh thu), chủ đầu tư
bất động sản, tổng thầu xây dựng dân dụng.

Để chung một cờ thì nhà thầu EPC điện gió sẽ mất nhánh Doanh thu là thứ
họ sống bằng nó.
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
    # Nhánh gốc; tắt nó là tắt cả cây con bên dưới.
    _RP_ENERGY_MENU_TONG_THAU = (
        'rp_owner_contract.menu_owner_revenue',
    )

    rp_energy_only_ui = fields.Boolean(
        string='Dự án năng lượng — ẩn phần bất động sản nhà ở',
        config_parameter='rp_energy.only_ui',
        help='Trong Project Master: ẩn Subzones / Buildings / Floors / '
             'Units / Unit Types và thay bằng "Phase". Nhà máy điện '
             'chia dự án theo giai đoạn và không có căn hộ để bán, nên '
             'các mục đó mở ra lúc nào cũng rỗng.\n'
             'CHỈ bật trên bản triển khai không quản lý nhà ở — bật ở '
             'nơi có dữ liệu căn hộ là cắt mất lối vào duy nhất tới '
             'khối dữ liệu đó. Chỉ ẩn, không xoá: tắt cờ là menu hiện '
             'lại nguyên vẹn.')
    rp_energy_owner_role = fields.Boolean(
        string='Vai chủ đầu tư — ẩn nhánh Doanh thu của tổng thầu',
        config_parameter='rp_energy.owner_role',
        help='Nhánh "Doanh thu" dựng cho vai TỔNG THẦU: hợp đồng với '
             'chủ đầu tư, nghiệm thu gửi chủ đầu tư, hoá đơn phát hành '
             'cho chủ đầu tư, thu tiền về. Chủ đầu tư không có nghiệp '
             'vụ nào trong số đó — doanh thu của họ đến từ khai thác '
             'công trình (nhà máy điện bán điện theo PPA).\n'
             'ĐỪNG bật cho nhà thầu EPC: họ sống bằng chính nhánh này.')

    def set_values(self):
        res = super().set_values()
        self._rp_energy_ap_dung_ui(self.rp_energy_only_ui,
                                   self.rp_energy_owner_role)
        return res

    @api.model
    def _rp_energy_co_bat(self, ten_tham_so):
        """Đọc cờ ra kiểu bool. Tham số lưu dạng chuỗi nên 'False' mà
        đưa thẳng vào `bool()` sẽ ra True."""
        raw = self.env['ir.config_parameter'].sudo().get_param(ten_tham_so)
        return str(raw or '').strip().lower() in ('true', '1', 'yes')

    @api.model
    def _rp_energy_ap_dung_ui(self, chi_nang_luong=None,
                              vai_chu_dau_tu=None):
        """Bật/tắt các nhánh menu theo hai cờ.

        Gọi không tham số thì tự đọc cờ — dùng cho `_register_hook`.
        """
        if chi_nang_luong is None:
            chi_nang_luong = self._rp_energy_co_bat('rp_energy.only_ui')
        if vai_chu_dau_tu is None:
            vai_chu_dau_tu = self._rp_energy_co_bat('rp_energy.owner_role')

        doi = [(x, not chi_nang_luong) for x in self._RP_ENERGY_MENU_NHA_O]
        doi += [(x, bool(chi_nang_luong))
                for x in self._RP_ENERGY_MENU_NANG_LUONG]
        doi += [(x, not vai_chu_dau_tu)
                for x in self._RP_ENERGY_MENU_TONG_THAU]
        for xmlid, bat in doi:
            # raise_if_not_found=False: module sở hữu menu có thể không
            # được cài ở bản triển khai này, và đó là chuyện bình thường.
            menu = self.env.ref(xmlid, raise_if_not_found=False)
            if menu and menu.active != bat:
                menu.sudo().active = bat
        # Menu nằm trong cache theo nhóm người dùng; không dọn thì người
        # đang mở phiên vẫn thấy cây menu cũ cho tới khi hết phiên.
        self.env.registry.clear_cache()
