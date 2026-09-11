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
    advance_dossier_id = fields.Many2one(
        'rp.loan.disbursement.dossier', string='Hồ sơ giải ngân',
        readonly=True, copy=False, index='btree_not_null',
        help='Có giá trị khi phiếu chi do NGÂN HÀNG giải ngân theo khế '
             'ước, không phải doanh nghiệp tự chi. Phần tiền này đã '
             'được đếm qua hồ sơ giải ngân nên KHÔNG cộng lại vào "Đã '
             'trả bằng tiền công ty".')
    advance_note_id = fields.Many2one(
        're.loan.note', string='Khế ước giải ngân',
        related='advance_dossier_id.disbursement_id.note_id',
        store=True, readonly=True,
        help='Khế ước mà ngân hàng giải ngân theo đó. Trống nếu doanh '
             'nghiệp tự chi.')
