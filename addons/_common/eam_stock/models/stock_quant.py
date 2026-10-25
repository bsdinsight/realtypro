# -*- coding: utf-8 -*-
"""Tồn kho mang theo nhà máy, để lọc và cộng được.

`stock.quant` của Odoo có sẵn `warehouse_id` nhưng KHÔNG LƯU — nó tính
lúc đọc. Trường không lưu thì không lọc nhanh được, không gom nhóm
được, và không đưa vào ô lọc bên trái được. Nên phải tự dựng một trường
có lưu, nối qua vị trí.
"""
from odoo import fields, models


class StockQuant(models.Model):
    _inherit = 'stock.quant'

    eam_plant_id = fields.Many2one(
        'eam.location', string='Nhà máy',
        related='location_id.eam_plant_id', store=True, index=True,
        help='Trống nghĩa là hàng đang nằm ở kho dùng chung, mọi nhà '
             'máy đều với tới được — không phải là thiếu dữ liệu.')
