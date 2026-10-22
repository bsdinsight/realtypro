# -*- coding: utf-8 -*-
"""Giá trị thuộc tính trên từng tài sản."""
from odoo import fields, models


class EamAsset(models.Model):
    _inherit = 'eam.asset'

    attrs = fields.Properties(
        string='Thông số kỹ thuật',
        definition='category_id.attr_definition',
        copy=True,
        help='Các ô ở đây do nhóm tài sản quyết định. Đổi nhóm thì bộ ô '
             'đổi theo — giá trị cũ không mất, nhưng chỉ hiện lại khi '
             'quay về đúng nhóm.')
