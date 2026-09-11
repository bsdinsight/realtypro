# -*- coding: utf-8 -*-
"""Phiếu chi gắn thẳng vào Tạm ứng (backlog 969).

Tạm ứng trả bằng tiền công ty trước đây chỉ được bấm "Đã thanh toán" —
tiền ra khỏi công ty mà sổ cái không có chứng từ nào. Nay mỗi đợt trả
sinh một phiếu chi thật, hạch toán Nợ 331 (trả trước người bán) / Có
tiền, và khi hoá đơn nhà thầu về thì phiếu chi đó cấn trừ thẳng vào
hoá đơn bằng cơ chế sẵn có của Odoo.
"""
from odoo import fields, models


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    advance_payment_id = fields.Many2one(
        'rp.advance.payment', string='Phiếu tạm ứng',
        readonly=True, copy=False, index='btree_not_null',
        help='Phiếu tạm ứng mà phiếu chi này thanh toán cho.')
