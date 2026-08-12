# -*- coding: utf-8 -*-
"""Nối BOQ (dự toán) với thư viện đơn giá — §5.3 của vn_cost_data_pattern.md.

Mở rộng `rp.boq.line` (rp_progress) để một dòng dự toán có thể:
- chọn **Item** từ Danh mục (rp.resource) thay vì gõ tay mô tả;
- kéo **đơn giá từ thư viện** (rp.unit.price = định mức × công bố giá) thay
  vì gõ số.

OPT-IN, KHÔNG PHÁ PROD: extension này chỉ nạp ở DB nào cài rp_cost_library
(dev). 4 DB production không có module này → rp.boq.line ở đó y nguyên.
`price_source` mặc định 'manual' → dòng cũ chạy như trước.
"""
from odoo import _, api, fields, models


class RpBoqLine(models.Model):
    _inherit = 'rp.boq.line'

    resource_id = fields.Many2one(
        'rp.resource', string='Item (tài nguyên)',
        help='Chọn Item từ Danh mục để lấy tên + đơn vị, thay vì gõ tay.')
    norm_id = fields.Many2one(
        'rp.norm', string='Định mức', domain="[('is_leaf','=',True)]",
        help='Mã hiệu định mức (tuỳ chọn) — để lần ngược hao phí.')
    unit_price_id = fields.Many2one(
        'rp.unit.price', string='Đơn giá thư viện',
        help='Đơn giá tổng hợp (định mức × công bố giá). Chọn để kéo giá.')
    price_source = fields.Selection([
        ('manual', 'Gõ tay'),
        ('library', 'Từ thư viện'),
    ], string='Nguồn giá', default='manual', required=True)

    @api.onchange('resource_id')
    def _onchange_resource_id(self):
        # LƯU Ý: rp.boq.line.uom_id là 'rp.progress.uom' còn
        # rp.resource.uom_id là 'uom.uom' — HAI hệ đơn vị khác model, không
        # gán chéo được. Nên chỉ điền mô tả; ĐVT người dùng tự chọn.
        # (Việc thống nhất/map 2 hệ UoM để sau.)
        for line in self:
            if line.resource_id and not line.description:
                line.description = line.resource_id.name

    @api.onchange('unit_price_id')
    def _onchange_unit_price_id(self):
        for line in self:
            up = line.unit_price_id
            if up:
                line.price_source = 'library'
                # đơn giá dự thầu = đã gói markup; nếu chưa có markup thì = trực tiếp
                line.unit_price = up.bid_price or up.direct_cost
                if up.norm_id:
                    line.norm_id = up.norm_id
                    if not line.description:
                        line.description = up.norm_id.name
