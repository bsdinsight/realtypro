# -*- coding: utf-8 -*-
"""Lô / sê-ri — thêm ngày sản xuất.

``product_expiry`` cho ngày hết hạn, ngày nên dùng trước, ngày cảnh báo —
nhưng KHÔNG có ngày sản xuất. Với dầu mỡ thì hạn dùng thường tính từ ngày
sản xuất chứ không từ ngày nhập kho, nên thiếu ô này là mất gốc tính.
"""
from odoo import fields, models


class StockLot(models.Model):
    _inherit = 'stock.lot'

    eam_mfg_date = fields.Date(
        string='Ngày sản xuất',
        help='Hạn dùng của dầu mỡ tính từ ngày sản xuất, không phải ngày '
             'nhập kho. Hàng nằm ở kho nhà cung cấp một năm rồi mới về '
             'thì hạn còn lại đã ngắn hơn nhiều so với tưởng.')
    eam_mfg_batch = fields.Char(string='Số lô của nhà sản xuất')
