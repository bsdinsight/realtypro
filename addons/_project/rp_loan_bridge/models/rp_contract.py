# -*- coding: utf-8 -*-
"""Inherit rp.contract: thêm phân bổ vay tài trợ HĐ."""
from odoo import api, fields, models


class RpContract(models.Model):
    _inherit = 'rp.contract'

    loan_allocation_ids = fields.One2many(
        'rp.loan.allocation', 'contract_id',
        string='Vay tài trợ HĐ')
    loan_allocation_count = fields.Integer(
        compute='_compute_loan_allocation_stats')
    loan_allocated_amount = fields.Monetary(
        string='Tổng vay tài trợ', compute='_compute_loan_allocation_stats',
        store=True,
        help='Tổng vay/lãi phân bổ tài trợ HĐ này.')

    @api.depends('loan_allocation_ids.amount_allocated')
    def _compute_loan_allocation_stats(self):
        for rec in self:
            rec.loan_allocation_count = len(rec.loan_allocation_ids)
            rec.loan_allocated_amount = sum(
                rec.loan_allocation_ids.mapped('amount_allocated'))
