from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class ReBuilding(models.Model):
    _name = 're.building'
    _description = 'Real Estate Building / Block'
    _inherit = ['realty.lifecycle.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'project_id, sequence, name'

    name = fields.Char(string='Building Name', required=True, tracking=True, translate=True)
    code = fields.Char(string='Code', required=True, tracking=True)
    sequence = fields.Integer(default=10)

    project_id = fields.Many2one('re.project', string='Project', required=True,
                                  tracking=True, ondelete='restrict')
    subzone_id = fields.Many2one('re.subzone', string='Subzone', tracking=True,
                                  ondelete='restrict',
                                  domain="[('project_id', '=', project_id)]")

    building_type = fields.Selection(
        [('residential', 'Residential'), ('commercial', 'Commercial'),
         ('mixed_use', 'Mixed-Use'), ('villa_zone', 'Villa Zone'),
         ('shophouse_block', 'Shophouse Block'),
         ('officetel', 'Officetel'), ('hotel', 'Hotel')],
        string='Building Type', tracking=True,
    )

    total_floors = fields.Integer(string='Above-Ground Floors', default=1)
    basement_count = fields.Integer(string='Basement Floors', default=0)
    elevator_count = fields.Integer(string='Elevators')
    parking_capacity = fields.Integer(string='Parking Capacity (Cars)')
    motorbike_capacity = fields.Integer(string='Motorbike Capacity')
    total_units_planned = fields.Integer(string='Total Units Planned')

    # Note: ``state`` and ``is_lifecycle_owner`` come from the lifecycle
    # mixin. The previous 4-state Construction Status has been replaced
    # by the unified 8-phase lifecycle.

    construction_start_date = fields.Date(string='Construction Start Date')
    expected_handover_date = fields.Date(string='Expected Handover Date')
    actual_handover_date = fields.Date(
        string='Actual Handover Date',
        help="Kept for backward compat; corresponds to product handover. "
             "Per-unit dates live on re.unit.product_handover_date and "
             "re.unit.certificate_handover_date.",
    )
    progress_percent = fields.Float(string='Construction Progress (%)', digits=(5, 2))

    legal_doc_type = fields.Selection(
        [('construction_permit', 'Construction Permit'),
         ('occupancy_permit', 'Occupancy Permit'),
         ('red_book', 'Red Book (Sổ đỏ)'),
         ('pink_book', 'Pink Book (Sổ hồng)'),
         ('construction_completion', 'Construction Completion Certificate')],
        string='Legal Document Type', tracking=True,
    )
    legal_doc_number = fields.Char(string='Legal Document Number')
    legal_doc_date = fields.Date(string='Legal Document Date')

    tagline = fields.Char(string='Tagline', translate=True)
    position_in_subzone = fields.Char(string='Position in Subzone', translate=True)
    floor_plate_image = fields.Image(string='Typical Floor Plate', max_width=2400, max_height=2400)

    description = fields.Text(string='Description', translate=True)
    image = fields.Image(string='Building Image', max_width=1920, max_height=1080)

    floor_ids = fields.One2many('re.floor', 'building_id', string='Floors')
    unit_ids = fields.One2many('re.unit', 'building_id', string='Units')

    floor_count = fields.Integer(compute='_compute_counts')
    unit_count = fields.Integer(compute='_compute_counts')
    available_unit_count = fields.Integer(compute='_compute_counts')

    active = fields.Boolean(default=True)

    # ------------------------------------------------------------------
    # Sale activity gating (Phase 4.0a) — see re.project for context
    # ------------------------------------------------------------------
    # For low-rise developments a "Dãy" (row of townhouses) is modeled as
    # a Building with a single floor; the same gating field applies.
    is_open_for_sale = fields.Boolean(
        string='Open for Sale Activities',
        default=False, tracking=True,
        help='Authorizes sale activities for units in this building. '
             'For low-rise developments a "Dãy" is one Building with one '
             'Floor; the flag works the same way. Combined (ANDed) with '
             'project- and subzone-level flags.',
    )

    _unique_code_per_project = models.Constraint(
        'UNIQUE(project_id, code)',
        'Building code must be unique within a project!',
    )

    @api.constrains('project_id', 'subzone_id')
    def _check_subzone_project(self):
        for rec in self:
            if rec.subzone_id and rec.subzone_id.project_id != rec.project_id:
                raise ValidationError(_(
                    'Subzone "%(subzone)s" does not belong to project "%(project)s".',
                    subzone=rec.subzone_id.name, project=rec.project_id.name,
                ))

    @api.constrains('progress_percent')
    def _check_progress(self):
        for rec in self:
            if rec.progress_percent < 0 or rec.progress_percent > 100:
                raise ValidationError(_('Progress percent must be between 0 and 100.'))

    @api.depends('floor_ids', 'unit_ids', 'unit_ids.state')
    def _compute_counts(self):
        for rec in self:
            rec.floor_count = len(rec.floor_ids)
            rec.unit_count = len(rec.unit_ids)
            rec.available_unit_count = len(rec.unit_ids.filtered(lambda u: u.state == 'available'))

    @api.depends('name', 'code', 'project_id.code', 'subzone_id.code')
    def _compute_display_name(self):
        for rec in self:
            parts = []
            if rec.project_id and rec.project_id.code:
                parts.append(rec.project_id.code)
            if rec.subzone_id and rec.subzone_id.code:
                parts.append(rec.subzone_id.code)
            if rec.code:
                parts.append(rec.code)
            prefix = '/'.join(parts) if parts else ''
            rec.display_name = f'{prefix} - {rec.name}' if prefix else (rec.name or '')

    @api.onchange('project_id')
    def _onchange_project_id(self):
        if self.subzone_id and self.subzone_id.project_id != self.project_id:
            self.subzone_id = False

    def action_view_floors(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Floors', 'res_model': 're.floor',
            'view_mode': 'list,form',
            'domain': [('building_id', '=', self.id)],
            'context': {'default_building_id': self.id, 'default_project_id': self.project_id.id},
        }

    def action_view_units(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Units', 'res_model': 're.unit',
            'view_mode': 'list,form,kanban',
            'domain': [('building_id', '=', self.id)],
            'context': {'default_building_id': self.id, 'default_project_id': self.project_id.id},
        }

    # ----- realty.lifecycle.mixin abstract -----

    def _expected_lifecycle_level(self):
        return 'building'

    # ----- entity-specific transition validation -----

    def action_open_for_sale(self):
        """Building-specific guard: must have at least one unit defined.

        Selling a building means selling its units; an empty building
        is a master-data oversight.
        """
        for rec in self:
            if not rec.unit_ids:
                raise UserError(_(
                    "Building %s cannot be opened for sale: no units "
                    "defined yet. Add floors and units first.",
                    rec.display_name,
                ))
        return super().action_open_for_sale()

    def action_to_operation(self):
        """Building-specific guard: all units should have product
        handover dates recorded before operation.
        """
        for rec in self:
            missing = rec.unit_ids.filtered(
                lambda u: not u.product_handover_date
            )
            if missing:
                raise UserError(_(
                    "Building %(name)s has %(n)d unit(s) without a "
                    "product handover date set; cannot move to "
                    "operation. Missing: %(codes)s",
                    name=rec.display_name,
                    n=len(missing),
                    codes=', '.join(missing.mapped('unit_code')[:5])
                          + ('…' if len(missing) > 5 else ''),
                ))
        return super().action_to_operation()
