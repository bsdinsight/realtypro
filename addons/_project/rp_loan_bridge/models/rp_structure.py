# -*- coding: utf-8 -*-
"""Inherit rp.structure: thêm phân bổ vay nhận về hạng mục."""
from odoo import api, fields, models


class RpStructure(models.Model):
    _inherit = 'rp.structure'

    loan_allocation_ids = fields.One2many(
        'rp.loan.allocation', 'structure_id',
        string='Vay phân bổ về hạng mục')
    loan_allocation_count = fields.Integer(
        compute='_compute_loan_allocation_stats')
    loan_allocated_amount = fields.Monetary(
        string='Tổng vay phân bổ', compute='_compute_loan_allocation_stats',
        store=True,
        help='Tổng vay/lãi phân bổ về hạng mục này (Σ amount_allocated).')

    @api.depends('loan_allocation_ids.amount_allocated')
    def _compute_loan_allocation_stats(self):
        for rec in self:
            rec.loan_allocation_count = len(rec.loan_allocation_ids)
            rec.loan_allocated_amount = sum(
                rec.loan_allocation_ids.mapped('amount_allocated'))
