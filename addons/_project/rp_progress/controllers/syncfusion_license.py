# -*- coding: utf-8 -*-
"""Controller expose Syncfusion license key cho frontend.

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
        '/rp_progress/syncfusion/license_key',
        type='json',
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
