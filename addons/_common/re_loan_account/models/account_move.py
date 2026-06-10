# -*- coding: utf-8 -*-
"""Liên kết bút toán → Khế ước nhận nợ để truy vết & báo cáo theo KW."""
from odoo import fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    loan_note_id = fields.Many2one(
        're.loan.note', string='Khế ước (KW)', index=True, copy=False,
        help='KW phát sinh bút toán này (giải ngân / lãi / trả nợ). Tự '
             'set khi user click Post trên dòng liên quan.')


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    loan_note_id = fields.Many2one(
        related='move_id.loan_note_id', store=True, index=True,
        string='Khế ước (KW)',
        help='KW của bút toán (related từ account.move). Cho phép pivot '
             'phát sinh theo KW.')
