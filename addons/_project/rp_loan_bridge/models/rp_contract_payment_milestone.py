# -*- coding: utf-8 -*-
"""Nguồn chi trả trên mốc thanh toán HĐ.

Thực tế VN: 90–100% thanh toán HĐ xây dựng của CĐT/tổng thầu đi qua
KHẾ ƯỚC vay (ngân hàng giải ngân thẳng cho nhà thầu theo hồ sơ
BBN + hoá đơn) — chỉ phần nhỏ chi bằng vốn tự có. Field này trả lời
"mốc này trả bằng tiền nào?" ngay trên Hồ sơ thanh toán.
"""
from odoo import fields, models


class RpContractPaymentMilestone(models.Model):
    _inherit = 'rp.contract.payment.milestone'

    funding_source = fields.Selection(
        [('equity', 'Vốn tự có'),
         ('loan', 'Khế ước vay')],
        string='Nguồn chi trả', tracking=False,
        help='Vốn tự có = chi từ tài khoản công ty (phiếu chi). '
             'Khế ước vay = ngân hàng giải ngân thẳng cho nhà thầu '
             'theo hồ sơ giải ngân (BBN + hoá đơn).')
    loan_note_id = fields.Many2one(
        're.loan.note', string='Khế ước (KW)', index=True,
        help='KW dùng để giải ngân cho mốc này (khi nguồn = Khế ước vay).')
