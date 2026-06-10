# -*- coding: utf-8 -*-
"""
Realty Party — family / personal relationship between two partners.

Used primarily to declare the spouse, parents, children, etc. of a
property Buyer or Co-owner, as required by Vietnamese sale contracts
(HĐMB). The relationship list lives inline on the partner form under
the "Realty Identity" tab.

Symmetry is NOT auto-mirrored: when partner A declares "Vợ/Chồng → B",
no inverse row is created on B automatically. Manual entry on both
sides if the user wants the inverse visible. This keeps the data
model simple and the audit trail explicit.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


# Relationship types relevant to Vietnamese HĐMB workflows.
# Kept intentionally small — covers spouse, direct parents/children,
# siblings, and a generic catch-all. Grandparents and in-laws can use
# 'other' with a free-text note.
RELATIONSHIP_TYPES = [
    ('spouse', 'Vợ/Chồng'),
    ('father', 'Cha'),
    ('mother', 'Mẹ'),
    ('child', 'Con'),
    ('sibling', 'Anh/Chị/Em ruột'),
    ('grandparent', 'Ông/Bà'),
    ('grandchild', 'Cháu'),
    ('other', 'Khác'),
]


class RePartnerRelationship(models.Model):
    _name = 're.partner.relationship'
    _description = 'Realty Party Relationship'
    _order = 'partner_id, relationship_type, related_partner_id'

    partner_id = fields.Many2one(
        'res.partner', string='Partner', required=True,
        ondelete='cascade', index=True,
    )
    related_partner_id = fields.Many2one(
        'res.partner', string='Related Partner', required=True,
        ondelete='restrict', index=True,
    )
    relationship_type = fields.Selection(
        RELATIONSHIP_TYPES, string='Relationship', required=True,
    )
    note = fields.Char(string='Note')

    # ------------------------------------------------------------------
    # Display name
    # ------------------------------------------------------------------
    @api.depends('partner_id', 'related_partner_id', 'relationship_type')
    def _compute_display_name(self):
        type_label = dict(RELATIONSHIP_TYPES)
        for rec in self:
            label = type_label.get(rec.relationship_type, rec.relationship_type or '')
            rec.display_name = "%s → %s (%s)" % (
                rec.partner_id.display_name or '',
                rec.related_partner_id.display_name or '',
                label,
            )

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------
    @api.constrains('partner_id', 'related_partner_id')
    def _check_not_self(self):
        for rec in self:
            if rec.partner_id and rec.related_partner_id \
                    and rec.partner_id.id == rec.related_partner_id.id:
                raise ValidationError(_(
                    "A partner cannot have a relationship to themselves."
                ))

    _partner_pair_uniq = models.Constraint(
        'UNIQUE (partner_id, related_partner_id)',
        'A relationship already exists between these two partners. '
        'Edit the existing record instead of creating a duplicate.',
    )
