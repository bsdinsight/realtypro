from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ReSubzone(models.Model):
    _name = 're.subzone'
    _description = 'Real Estate Subzone (Phân khu)'
    _inherit = ['realty.lifecycle.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'project_id, sequence, name'

    name = fields.Char(string='Subzone Name', required=True, tracking=True, translate=True)
    code = fields.Char(string='Code', required=True, tracking=True)
    sequence = fields.Integer(default=10)

    project_id = fields.Many2one('re.project', string='Project', required=True,
                                  tracking=True, ondelete='cascade')

    subzone_type = fields.Selection(
        [('apartment', 'Apartment Block'), ('villa', 'Villa Zone'),
         ('townhouse', 'Townhouse Zone'), ('shophouse', 'Shophouse Zone'),
         ('mixed', 'Mixed-Use'), ('commercial', 'Commercial Zone')],
        string='Subzone Type', tracking=True,
    )

    area_ha = fields.Float(string='Total Area (ha)', digits=(10, 2))
    built_area_ha = fields.Float(string='Built Area (ha)', digits=(10, 2))
    green_area_percent = fields.Float(string='Green Area (%)', digits=(5, 2))
    total_units_planned = fields.Integer(string='Total Units Planned')

    tagline = fields.Char(string='Tagline', translate=True)
    theme = fields.Char(string='Theme', translate=True)
    expected_handover_date = fields.Date(string='Expected Handover Date')

    # Note: `state` and `is_lifecycle_owner` come from the
    # ``realty.lifecycle.mixin`` inherit above; the old per-subzone
    # ``Sales Status`` selection has been removed in favour of the
    # unified 8-phase lifecycle.

    description = fields.Html(string='Description', translate=True)
    image = fields.Image(string='Subzone Image', max_width=1920, max_height=1080)

    building_ids = fields.One2many('re.building', 'subzone_id', string='Buildings')
    unit_ids = fields.One2many('re.unit', 'subzone_id', string='Units')

    building_count = fields.Integer(compute='_compute_counts')
    unit_count = fields.Integer(compute='_compute_counts')
    available_unit_count = fields.Integer(compute='_compute_counts')

    active = fields.Boolean(default=True)

    # ------------------------------------------------------------------
    # Sale activity gating (Phase 4.0a) — see re.project for context
    # ------------------------------------------------------------------
    is_open_for_sale = fields.Boolean(
        string='Open for Sale Activities',
        default=False, tracking=True,
        help='Authorizes sale activities for units in this subzone. '
             'Combined (ANDed) with the project- and building-level flags.',
    )

    _unique_code_per_project = models.Constraint(
        'UNIQUE(project_id, code)',
        'Subzone code must be unique within a project!',
    )

    # ----- mixin abstract -----

    def _expected_lifecycle_level(self):
        return 'subzone'

    # ----- entity-specific transition validation -----

    def action_open_for_sale(self):
        """Subzone-specific guard: must have either buildings or units.

        A subzone is meaningless to "open for sale" if it has no
        children to sell.
        """
        for rec in self:
            if not rec.building_ids and not rec.unit_ids:
                raise UserError(_(
                    "Subzone %s cannot be opened for sale: no buildings "
                    "or units defined yet.",
                    rec.display_name,
                ))
        return super().action_open_for_sale()

    def action_to_operation(self):
        """Subzone-specific guard: all child units should have
        ``product_handover_date`` recorded.

        Soft check — we only require product handover dates exist;
        certificate dates are routinely months later, so we don't
        require them here.
        """
        for rec in self:
            missing = rec.unit_ids.filtered(
                lambda u: not u.product_handover_date
            )
            if missing:
                raise UserError(_(
                    "Subzone %(name)s has %(n)d unit(s) without a "
                    "product handover date set; cannot move to "
                    "operation. Missing: %(codes)s",
                    name=rec.display_name,
                    n=len(missing),
                    codes=', '.join(missing.mapped('unit_code')[:5])
                          + ('…' if len(missing) > 5 else ''),
                ))
        return super().action_to_operation()

    @api.depends('building_ids', 'unit_ids', 'unit_ids.state')
    def _compute_counts(self):
        for rec in self:
            rec.building_count = len(rec.building_ids)
            rec.unit_count = len(rec.unit_ids)
            rec.available_unit_count = len(rec.unit_ids.filtered(lambda u: u.state == 'available'))

    @api.depends('name', 'code', 'project_id.code')
    def _compute_display_name(self):
        for rec in self:
            if rec.project_id and rec.code:
                rec.display_name = f'{rec.project_id.code}/{rec.code} - {rec.name}'
            else:
                rec.display_name = rec.name or ''

    def action_view_buildings(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Buildings', 'res_model': 're.building',
            'view_mode': 'list,form',
            'domain': [('subzone_id', '=', self.id)],
            'context': {'default_subzone_id': self.id, 'default_project_id': self.project_id.id},
        }

    def action_view_units(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Units', 'res_model': 're.unit',
            'view_mode': 'list,form,kanban',
            'domain': [('subzone_id', '=', self.id)],
            'context': {'default_subzone_id': self.id, 'default_project_id': self.project_id.id},
        }
