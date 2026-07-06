# -*- coding: utf-8 -*-
"""Pledge: tỷ lệ cho vay + đóng góp vào borrowing base."""
from odoo import api, fields, models


class ReLoanCollateralPledge(models.Model):
    _inherit = 're.loan.collateral.pledge'

    advance_rate = fields.Float(
        string='Tỷ lệ cho vay (%)',
        compute='_compute_advance_rate', store=True, readonly=False,
        help='Mặc định theo loại TSBĐ — sửa được từng pledge (cùng là '
             'phải thu nhưng CĐT uy tín khác nhau → tỷ lệ khác nhau). '
             '0 = không tính vào borrowing base.')
    base_contribution = fields.Monetary(
        string='Đóng góp base',
        compute='_compute_base_contribution', store=True,
        currency_field='currency_id',
        help='= (Giá trị đảm bảo nếu khai, else giá trị hiện hành TS) '
             '× tỷ lệ cho vay. Chỉ tính pledge đang thế chấp.')

    @api.depends('collateral_id.type_id.advance_rate')
    def _compute_advance_rate(self):
        for rec in self:
            if not rec.advance_rate:
                rec.advance_rate = (
                    rec.collateral_id.type_id.advance_rate or 0.0)

    @api.depends('advance_rate', 'secured_amount', 'state',
                 'collateral_id.value_current')
    def _compute_base_contribution(self):
        for rec in self:
            if rec.state != 'active' or not rec.advance_rate:
                rec.base_contribution = 0.0
                continue
            base_value = rec.secured_amount or \
                rec.collateral_id.value_current
            rec.base_contribution = base_value * rec.advance_rate / 100.0
