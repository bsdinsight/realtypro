# -*- coding: utf-8 -*-
"""rp.contractor.specialty — Chuyên môn nhà thầu.

Master list of contractor specialties. Used as M2M tag on rp.contractor
to indicate which construction trades a contractor can perform.

Default seed contains 20 Vietnamese construction specialties loaded
via data XML on module install. Users can add custom specialties
post-install through the menu UI.

Examples: Móng - Cọc, Kết cấu, MEP, Facade, PCCC, Cảnh quan, etc.
"""

from odoo import fields, models


class RpContractorSpecialty(models.Model):
    _name = 'rp.contractor.specialty'
    _description = 'Contractor Specialty / Chuyên môn nhà thầu'
    _order = 'sequence, code, name'

    name = fields.Char(string='Name', required=True, translate=True)
    code = fields.Char(string='Code')
    sequence = fields.Integer(default=10)
    description = fields.Text()
    active = fields.Boolean(default=True)

    _unique_code = models.Constraint(
        'UNIQUE(code)',
        'A specialty code must be unique.',
    )
