# -*- coding: utf-8 -*-
from odoo import fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    cost_allocation_ids = fields.One2many(
        'rp.cost.allocation', 'move_id',
        string='Phân bổ chi phí (AC)',
        help='Các dòng split chi phí của hóa đơn này cho nhiều đầu việc.')
