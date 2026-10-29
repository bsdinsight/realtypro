# -*- coding: utf-8 -*-
"""Model/nền tảng thiết bị — để biết phụ tùng này lắp được cho máy nào.

``eam.asset.model_ref`` đang là chữ tự do. Chữ tự do thì "V150-4.2MW",
"V150 4,2 MW" và "v150" là ba thứ khác nhau với máy tính, nên không lọc
được "phụ tùng nào lắp được cho nền tảng này" — mà đó đúng là câu người
giữ kho hỏi trước khi xuất.

Nên có một danh mục nhỏ, và phụ tùng trỏ vào đó. Cố ý KHÔNG đụng vào
``model_ref`` của tài sản ở bước này: đổi cột đang mang dữ liệu sống là
việc riêng, làm lẫn vào đây thì hỏng cả hai.
"""
from odoo import api, fields, models


class EamEquipmentModel(models.Model):
    _name = 'eam.equipment.model'
    _description = 'Model / nền tảng thiết bị'
    _order = 'manufacturer_id, name'

    # Tên nền tảng thiết bị là TỪ VỰNG NGÀNH ('Nền tảng 4,0 MW · rô-to
    # 150 m'), không phải tên khách tự đặt — mở dịch.
    name = fields.Char(string='Tên model', required=True, translate=True)
    code = fields.Char(string='Mã')
    manufacturer_id = fields.Many2one(
        'res.partner', string='Hãng chế tạo', ondelete='restrict')
    category_id = fields.Many2one(
        'eam.asset.category', string='Loại cấu phần',
        help='Model này thuộc loại cấu phần nào — tua-bin, máy biến áp, '
             'bộ biến đổi…')
    rated_kw = fields.Float(string='Công suất định mức (kW)', digits=(16, 1))
    note = fields.Text(string='Ghi chú')
    product_ids = fields.Many2many(
        'product.template', 'eam_model_product_rel', 'model_id', 'product_id',
        string='Phụ tùng lắp được')
    product_count = fields.Integer(
        string='Số phụ tùng', compute='_compute_product_count')
    active = fields.Boolean(default=True)

    @api.depends('product_ids')
    def _compute_product_count(self):
        for m in self:
            m.product_count = len(m.product_ids)

    @api.depends('name', 'manufacturer_id')
    def _compute_display_name(self):
        for m in self:
            m.display_name = (
                '%s — %s' % (m.manufacturer_id.name, m.name)
                if m.manufacturer_id else (m.name or ''))
