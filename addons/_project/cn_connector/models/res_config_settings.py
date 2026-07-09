# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    cn_hub_url = fields.Char(
        string='Construction Network URL',
        config_parameter='cn_connector.hub_url',
        help='Vd https://cnhub.realtypro.vn')
    cn_hub_api_key = fields.Char(
        string='Network API Key',
        config_parameter='cn_connector.api_key',
        help='Khớp với System Parameter cn_hub.api_key trên Hub.')
