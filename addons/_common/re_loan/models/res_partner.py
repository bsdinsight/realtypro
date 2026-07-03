# -*- coding: utf-8 -*-
"""Extend res.partner (NH) — config phí KW theo ngân hàng (CC1 #9)."""
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    kw_fee_rate = fields.Float(
        string='% phí KW trên lãi', digits=(5, 2),
        help='Phí khế ước nhận nợ mặc định của NH này, tính bằng % '
             'trên tiền lãi. Auto-load khi tạo KW chọn cách tính phí '
             '"% trên lãi" — sửa được per-KW.')
