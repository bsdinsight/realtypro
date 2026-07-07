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
    appraiser_id = fields.Many2one(
        'res.partner', string='Tổ chức thẩm định giá',
        domain="[('is_appraiser', '=', True)]",
        context={'default_is_appraiser': True, 'default_is_company': True},
        help='Chọn từ danh mục đối tác có cờ "Tổ chức thẩm định giá" — '
             'gõ tên mới rồi Create để thêm nhanh.')
    appraiser = fields.Char(
        string='Người định giá (text)',
        help='Trường text cũ — giữ để xem dữ liệu lịch sử; bản ghi mới '
             'dùng dropdown Tổ chức thẩm định giá.')
    date_valid_until = fields.Date(
        string='Ngày hết hạn định giá',
        help='Chứng thư định giá thường có hiệu lực 6-12 tháng — NH '
             'yêu cầu định giá lại khi hết hạn (CC1 #15).')
    is_expired = fields.Boolean(
        string='Hết hạn', compute='_compute_is_expired',
        help='True khi quá Ngày hết hạn định giá.')
    attachment_ids = fields.Many2many(
        'ir.attachment', 're_loan_collateral_valuation_att_rel',
        'valuation_id', 'attachment_id',
        string='Tài liệu đính kèm',
        help='Upload file chứng thư định giá (PDF/scan) — CC1 #15.')
    note = fields.Char(string='Ghi chú')

    def _compute_is_expired(self):
        today = fields.Date.context_today(self)
        for rec in self:
            rec.is_expired = bool(
                rec.date_valid_until and rec.date_valid_until < today)
    currency_id = fields.Many2one(
        related='collateral_id.currency_id', store=True, readonly=True)
    company_id = fields.Many2one(
        related='collateral_id.company_id', store=True, readonly=True)

    @api.constrains('amount')
    def _check_amount(self):
        for rec in self:
            if rec.amount < 0:
                raise ValidationError(_("Giá trị định giá không được âm."))
