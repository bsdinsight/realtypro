# -*- coding: utf-8 -*-
"""Thanh toán của Chủ đầu tư cho tổng thầu.

KTT ghi nhận tiền CĐT trả về (thường qua TK phong tỏa tại NH cho vay).
Mỗi khoản trả làm GIẢM khoản phải thu → giảm giá trị TSBĐ quyền đòi nợ.
"""
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class RpOwnerPayment(models.Model):
    _name = 'rp.owner.payment'
    _description = 'Thanh toán của Chủ đầu tư'
    _order = 'date desc, id desc'

    contract_id = fields.Many2one(
        'rp.owner.contract', string='HĐ với CĐT', required=True,
        ondelete='cascade', index=True)
    project_id = fields.Many2one(
        related='contract_id.project_id', store=True, index=True)
    owner_id = fields.Many2one(
        related='contract_id.owner_id', store=True, string='Chủ đầu tư')
    currency_id = fields.Many2one(
        related='contract_id.currency_id', store=True)
    company_id = fields.Many2one(
        related='contract_id.company_id', store=True)

    date = fields.Date(
        string='Ngày nhận tiền', required=True,
        default=fields.Date.context_today)
    amount = fields.Monetary(string='Số tiền', required=True)
    payment_type = fields.Selection(
        [('advance', 'CĐT tạm ứng'),
         ('progress', 'Theo sản lượng'),
         ('final', 'Quyết toán'),
         ('other', 'Khác')],
        string='Loại', default='progress', required=True)
    reference = fields.Char(
        string='Chứng từ', help='Số UNC / giấy báo có của NH.')
    note = fields.Char(string='Ghi chú')

    @api.constrains('amount')
    def _check_amount(self):
        for rec in self:
            if not rec.amount:
                raise ValidationError(
                    'Số tiền phải khác 0 (âm = hoàn trả CĐT).')
