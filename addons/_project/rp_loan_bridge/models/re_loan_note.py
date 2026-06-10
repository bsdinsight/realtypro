# -*- coding: utf-8 -*-
"""Inherit re.loan.note: thêm allocation_ids + tổng phân bổ."""
from odoo import api, fields, models


class ReLoanNote(models.Model):
    _inherit = 're.loan.note'

    allocation_ids = fields.One2many(
        'rp.loan.allocation', 'note_id', string='Phân bổ công trình')
    allocation_count = fields.Integer(compute='_compute_allocation_stats')
    allocation_total_principal = fields.Monetary(
        string='Σ phân bổ gốc', compute='_compute_allocation_stats',
        store=True)
    allocation_total_interest = fields.Monetary(
        string='Σ phân bổ lãi', compute='_compute_allocation_stats',
        store=True)

    @api.depends('allocation_ids.amount_allocated', 'allocation_ids.base')
    def _compute_allocation_stats(self):
        for rec in self:
            rec.allocation_count = len(rec.allocation_ids)
            principal = 0.0
            interest = 0.0
            for a in rec.allocation_ids:
                if a.base == 'principal':
                    principal += a.amount_allocated
                elif a.base == 'interest':
                    interest += a.amount_allocated
                else:  # both → chia đôi (ước lượng)
                    principal += a.amount_allocated * 0.5
                    interest += a.amount_allocated * 0.5
            rec.allocation_total_principal = principal
            rec.allocation_total_interest = interest
