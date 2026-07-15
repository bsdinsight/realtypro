# -*- coding: utf-8 -*-
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_project_owner = fields.Boolean(
        string='Chủ đầu tư',
        help='Đối tác đóng vai Chủ đầu tư trong các HĐ đầu ra.')
