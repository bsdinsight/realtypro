# -*- coding: utf-8 -*-
"""Định giá tài sản thế chấp — nhiều lần theo thời gian."""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ReLoanCollateralValuation(models.Model):
    _name = 're.loan.collateral.valuation'
    _description = 'Định giá tài sản thế chấp'
    _order = 'date desc, id desc'

    collateral_id = fields.Many2one(
        're.loan.collateral', string='Tài sản', required=True,
        ondelete='cascade')
    date = fields.Date(
        string='Ngày định giá', required=True,
        default=fields.Date.context_today)
    amount = fields.Monetary(string='Giá trị', required=True)
    method = fields.Selection(
        [('market', 'So sánh thị trường'),
         ('cost', 'Chi phí'),
         ('income', 'Thu nhập'),
         ('appraisal', 'Tổ chức thẩm định giá')],
        string='Phương pháp', default='appraisal', required=True)
    appraiser = fields.Char(string='Tổ chức / Người định giá')
    note = fields.Char(string='Ghi chú')
    currency_id = fields.Many2one(
        related='collateral_id.currency_id', store=True, readonly=True)
    company_id = fields.Many2one(
        related='collateral_id.company_id', store=True, readonly=True)

    @api.constrains('amount')
    def _check_amount(self):
        for rec in self:
            if rec.amount < 0:
                raise ValidationError(_("Giá trị định giá không được âm."))
