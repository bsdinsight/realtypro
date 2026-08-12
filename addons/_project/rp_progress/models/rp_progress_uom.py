# -*- coding: utf-8 -*-
"""
Đơn vị tính (UOM) dùng trong BBN KLCV — master data riêng cho ngành xây
dựng (m², m³, kg, tấn, bộ, cái, mét dài, …). Tách riêng khỏi uom.uom
chuẩn Odoo (vốn dùng cho sales/inventory) — đặc thù VN construction.
"""
from odoo import fields, models


class RpProgressUom(models.Model):
    _name = 'rp.progress.uom'
    _description = 'Đơn vị tính (Xây dựng)'
    _order = 'sequence, name'

    name = fields.Char(string='Tên', required=True, translate=True)
    code = fields.Char(string='Mã', required=True,
                       help='Mã viết tắt (vd m2, m3, kg, ton).')
    sequence = fields.Integer(string='Sequence', default=10)
    description = fields.Char(string='Diễn giải')
    active = fields.Boolean(default=True)

    # Odoo 19 BỎ `_sql_constraints` — khai kiểu cũ không tạo constraint.
    _code_unique = models.Constraint(
        'unique(code)', 'Mã đơn vị tính phải duy nhất.')
