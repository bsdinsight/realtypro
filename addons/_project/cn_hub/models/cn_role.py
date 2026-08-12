# -*- coding: utf-8 -*-
"""Vai trò của công ty trên Network.

Network là MỘT sàn duy nhất (gộp nhà thầu + nhà cung ứng), nên một công ty
phải được là **nhiều vai cùng lúc** — ở VN rất nhiều đơn vị vừa bán vật tư
vừa nhận thi công. Vì vậy vai trò là danh mục nhiều-nhiều, KHÔNG phải một
Selection chọn-một, và cũng không tách thành 2 sàn riêng.

Dữ liệu mẫu: Thi công · Vật tư · Nhân công · Nội thất · Dịch vụ
(thêm vai mới = thêm record, không phải sửa code).
"""
from odoo import fields, models


class CnRole(models.Model):
    _name = 'cn.role'
    _description = 'Vai trò trên Network (thi công / vật tư / ...)'
    _order = 'sequence, id'

    name = fields.Char(string='Vai trò', required=True, translate=True)
    code = fields.Char(string='Mã', required=True)
    description = fields.Char(string='Mô tả ngắn', translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    partner_count = fields.Integer(
        string='Số công ty', compute='_compute_partner_count')

    _uniq_code = models.Constraint(
        'unique(code)', 'Mã vai trò phải là duy nhất.')

    def _compute_partner_count(self):
        Partner = self.env['res.partner']
        for r in self:
            r.partner_count = Partner.search_count(
                [('cn_role_ids', 'in', r.id)])
