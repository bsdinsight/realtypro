# -*- coding: utf-8 -*-
"""
Liên kết res.bank ↔ res.partner để filter chi nhánh theo entity ngân hàng.

res.bank ở Odoo chuẩn là master "Bank Institution" (tên + BIC). res.partner
với is_bank=True là entity pháp nhân ngân hàng (đối tác cho vay). Một entity
NH có thể có nhiều chi nhánh (nhiều res.bank). Field partner_id mới cho phép
filter res.bank theo NH đã chọn (vd HĐTD chọn SHB → chi nhánh chỉ hiện SHB).
"""
from odoo import fields, models


class ResBank(models.Model):
    _inherit = 'res.bank'

    partner_id = fields.Many2one(
        'res.partner', string='Bank Entity',
        domain="[('is_bank', '=', True)]", index=True,
        help='Pháp nhân ngân hàng (res.partner is_bank=True) mà res.bank '
             'này thuộc về. Dùng để filter chi nhánh theo NH trên các '
             'form HĐTD, tài khoản…')
