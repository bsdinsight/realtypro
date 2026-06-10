# -*- coding: utf-8 -*-
"""Bridge account.move (vendor bill) ↔ rp.contract.payment.milestone."""
from odoo import fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    payment_milestone_id = fields.Many2one(
        'rp.contract.payment.milestone', string='Đợt thanh toán HĐ',
        copy=False, index=True,
        help='Vendor bill này gắn với đợt thanh toán nào của HĐ nhà thầu.')
