# -*- coding: utf-8 -*-
"""Controller cấp khoá giấy phép Syncfusion cho phía trình duyệt.

License key lưu ở ir.config_parameter `syncfusion.license_key`. Admin
set qua menu Settings → System Parameters (hoặc qua Settings view của
rp_progress).

Endpoint trả về key CHỈ cho user đã authenticated. Public user reject.
KHÔNG log key vào audit / response — chỉ trả raw value.
"""
from odoo import http
from odoo.http import request


class SyncfusionLicenseController(http.Controller):

    @http.route(
        [
            '/bsd_syncfusion/license_key',
            # GIỮ route cũ. Trình duyệt đang mở vẫn giữ mã JS cũ trong
            # bộ nhớ đệm và sẽ gọi địa chỉ này; bỏ đi là màn Gantt của
            # người đang làm việc gãy ngay giữa chừng, mà họ không hiểu
            # vì sao. Xoá được khi mọi phiên đã nạp lại.
            '/rp_progress/syncfusion/license_key',
        ],
        type='jsonrpc',
        auth='user',
        methods=['POST'],
    )
    def get_license_key(self):
        """Trả license key Syncfusion cho EJ2 init.

        Return:
            {'key': '<license>', 'configured': True}
            {'key': '',          'configured': False}  # admin chưa set
        """
        key = request.env['ir.config_parameter'].sudo().get_param(
            'syncfusion.license_key', '').strip()
        return {
            'key': key,
            'configured': bool(key),
        }
