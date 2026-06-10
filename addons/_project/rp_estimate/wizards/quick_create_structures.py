# -*- coding: utf-8 -*-
"""Wizard: bulk-create Hạng mục dự án for a project.

Opened from a project form. User picks a subzone and adds rows of
(name, code, type, planned figures). Wizard creates rp.structure
records in one shot.

Reduces clicks for projects with many towers / villas / units.
"""

from odoo import api, fields, models
from odoo.exceptions import UserError


class RpWizardQuickCreateStructures(models.TransientModel):
    _name = 'rp.wizard.quick.create.structures'
    _description = 'Quick Create Project Structures'

    project_id = fields.Many2one(
        're.project', string='Project',
        required=True,
    )
    subzone_id = fields.Many2one(
        're.subzone', string='Subzone',
        required=True,
        domain="[('project_id', '=', project_id)]",
    )
    default_structure_type = fields.Selection(
        selection=lambda self: self.env['rp.structure']._fields['structure_type'].selection,
        string='Default Type',
        default='tower',
    )
    line_ids = fields.One2many(
        'rp.wizard.quick.create.structures.line',
        'wizard_id',
        string='Structures to create',
    )

    def action_create(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError('Add at least one structure to create.')

        Structure = self.env['rp.structure']
        created = Structure
        for line in self.line_ids:
            vals = {
                'project_id': self.project_id.id,
                'subzone_id': self.subzone_id.id,
                'structure_level': 'item',
                'structure_type': line.structure_type or self.default_structure_type,
                'name': line.name,
                'code': line.code,
                'planned_gfa': line.planned_gfa,
                'planned_units': line.planned_units,
                'planned_floors': line.planned_floors,
            }
            created += Structure.create(vals)

        return {
            'type': 'ir.actions.act_window',
            'name': 'Created Structures',
            'res_model': 'rp.structure',
            'view_mode': 'list,form',
            'domain': [('id', 'in', created.ids)],
            'target': 'current',
        }


class RpWizardQuickCreateStructuresLine(models.TransientModel):
    _name = 'rp.wizard.quick.create.structures.line'
    _description = 'Quick Create Structure - Line'
    _order = 'sequence, id'

    wizard_id = fields.Many2one(
        'rp.wizard.quick.create.structures',
        required=True, ondelete='cascade',
    )
    sequence = fields.Integer(default=10)
    name = fields.Char(string='Name', required=True)
    code = fields.Char(string='Code')
    structure_type = fields.Selection(
        selection=lambda self: self.env['rp.structure']._fields['structure_type'].selection,
    )
    planned_gfa = fields.Float(string='GFA (m²)')
    planned_units = fields.Integer(string='Units')
    planned_floors = fields.Integer(string='Floors')
