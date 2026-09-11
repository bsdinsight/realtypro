# -*- coding: utf-8 -*-
"""Phiếu chi biết mình thuộc chứng thư bảo lãnh nào (backlog 969).

Mở một phiếu chi ra mà không có đường quay lại chứng thư thì người
dùng phải tự đoán từ câu ghi chú — mà câu đó chỉ là chữ, không bấm
được.
"""
from odoo import fields, models


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    guarantee_payment_id = fields.Many2one(
        're.bank.guarantee.payment', string='Đợt thanh toán BL',
        readonly=True, copy=False, index='btree_not_null',
        ondelete='set null')
    guarantee_id = fields.Many2one(
        're.bank.guarantee', string='Chứng thư BL',
        related='guarantee_payment_id.guarantee_id',
        store=True, readonly=True)
    guarantee_refund_id = fields.Many2one(
        're.bank.guarantee', string='Hoàn ký quỹ cho BL',
        readonly=True, copy=False, index='btree_not_null',
        ondelete='set null',
        help='Có giá trị với phiếu THU ghi nhận ngân hàng trả lại tiền '
             'ký quỹ khi chứng thư kết thúc.')
