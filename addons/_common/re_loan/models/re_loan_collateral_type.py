# -*- coding: utf-8 -*-
"""
Loại tài sản thế chấp (collateral type) — master data.

Master nhỏ, seed sẵn các loại TS thế chấp phổ biến của doanh nghiệp xây
dựng VN. Module rf_collateral (phase L3) sẽ tham chiếu loại này cho từng
tài sản thế chấp cụ thể.
"""
from odoo import fields, models


class ReLoanCollateralType(models.Model):
    _name = 're.loan.collateral.type'
    _description = 'Loại tài sản thế chấp'
    _order = 'sequence, name'

    name = fields.Char(string='Type Name', required=True, translate=True)
    code = fields.Char(string='Code', copy=False)
    sequence = fields.Integer(string='Sequence', default=10)
    note = fields.Char(string='Note')
    active = fields.Boolean(default=True)

    _code_uniq = models.Constraint(
        'UNIQUE (code)',
        'Collateral type code must be unique.',
    )
