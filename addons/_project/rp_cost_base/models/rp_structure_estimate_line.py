# -*- coding: utf-8 -*-
"""rp.structure.estimate.line — Khái toán inline per structure (v1.4.3-r4).

Each line captures: structure × category × amount.

Single-source-of-truth for cost entries in Phase 2. User opens any
rp.structure form (Hạng mục dự án or Sub-hạng mục), goes to the
"Khái toán" tab, and enters one line per cost category.

Aggregation views:
- Per-structure: sum line.amount → estimate_total on rp.structure
- Per-project: pivot view at menu Estimate → Khái toán shows
  rows=structure × cols=category × cells=amount with totals

Unique constraint: (structure_id, category_id). User cannot create
two lines for the same category on the same structure. If user wants
to express two separate amounts of the same category, they should
combine them into one line or split via the description/note.

Phase 3 will add ``rp.boq.line`` (BOQ items with qty × unit price)
and replace this Khái toán line's amount with a computed rollup from
BOQ. This module's estimate line stays as Phase 2 Khái toán entry
point even after Phase 3 lands.
"""

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class RpStructureEstimateLine(models.Model):
    _name = 'rp.structure.estimate.line'
    _description = 'Khái toán Line / Structure Cost Estimate Line'
    _order = 'structure_id, category_sequence, category_id, id'

    # ----- Anchor on structure (parent)
    structure_id = fields.Many2one(
        'rp.structure', string='Hạng mục',
        required=True, ondelete='cascade', index=True,
    )
    project_id = fields.Many2one(
        related='structure_id.project_id', store=True, index=True,
    )
    subzone_id = fields.Many2one(
        related='structure_id.subzone_id', store=True, index=True,
    )
    parent_structure_id = fields.Many2one(
        related='structure_id.parent_id', store=True, index=True,
        string='Hạng mục cha',
    )
    structure_level = fields.Selection(
        related='structure_id.structure_level', store=True,
    )
    currency_id = fields.Many2one(
        related='structure_id.currency_id', store=True,
    )

    # ----- Category
    category_id = fields.Many2one(
        'rp.cost.category', string='Cost Category',
        required=True, ondelete='restrict', index=True,
        domain="[('project_id', '=', project_id)]",
        help='Cost category from the project\'s category tree. '
             'Must belong to the same project as the structure.',
    )
    category_sequence = fields.Integer(
        related='category_id.sequence', store=True, index=True,
    )

    # ----- Amount
    amount = fields.Monetary(
        string='Số tiền',
        currency_field='currency_id', required=True, default=0.0,
    )
    description = fields.Char(
        string='Mô tả',
        translate=True,
        help='Short description of what this cost covers.',
    )
    note = fields.Text(string='Ghi chú')

    # ===== Constraints =====

    @api.constrains('category_id', 'structure_id')
    def _check_category_same_project(self):
        for line in self:
            if line.category_id.project_id != line.structure_id.project_id:
                raise ValidationError(
                    f'[{line.structure_id.display_name}] Cost category '
                    f'"{line.category_id.display_name}" belongs to a '
                    f'different project. Category must be from the same '
                    f'project as the structure.'
                )

    @api.constrains('amount')
    def _check_amount_non_negative(self):
        for line in self:
            if line.amount < 0:
                raise ValidationError(
                    f'Estimate amount cannot be negative '
                    f'(got {line.amount} on {line.structure_id.display_name}).'
                )

    _unique_category_per_structure = models.Constraint(
        'UNIQUE(structure_id, category_id)',
        'Mỗi cost category chỉ có thể xuất hiện một lần trên mỗi hạng mục.',
    )
