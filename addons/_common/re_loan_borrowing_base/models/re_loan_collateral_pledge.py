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
        help='= min(Giá trị đảm bảo theo HĐ thế chấp, Giá trị hiện hành '
             'TS theo định giá mới nhất) × tỷ lệ cho vay. Định giá lại '
             'TSĐB GIẢM → base giảm theo (khả dụng HĐTD/facility giảm); '
             'tăng thì vẫn trần ở giá trị đảm bảo đã ký (muốn tăng phải '
             'ký phụ lục). TS chưa định giá → dùng giá trị đảm bảo. '
             'Chỉ tính pledge đang thế chấp.')

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
            value_current = rec.collateral_id.value_current
            base_value = rec.secured_amount or value_current
            # Định giá lại TSĐB thấp hơn giá trị đảm bảo theo HĐ thế
            # chấp → NH chỉ cho vay trên giá trị thực → cap theo định
            # giá mới nhất. Chỉ cap khi TS ĐÃ có định giá (chưa định
            # giá thì tin giá trị HĐ thế chấp).
            if value_current:
                base_value = min(base_value, value_current)
            rec.base_contribution = base_value * rec.advance_rate / 100.0
