from odoo import api, fields, models


class ReProject(models.Model):
    _name = 're.project'
    _description = 'Real Estate Project'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, name'

    # IDENTIFICATION
    name = fields.Char(string='Project Name', required=True, tracking=True, translate=True)
    code = fields.Char(string='Project Code', required=True, tracking=True, copy=False,
                       help='Short code used in unit codes (e.g., DSM)')
    sequence = fields.Integer(default=10)

    # CLASSIFICATION
    project_type = fields.Selection(
        [('residential', 'Residential'), ('commercial', 'Commercial'),
         ('mixed_use', 'Mixed-Use'), ('villa', 'Villa'),
         ('townhouse', 'Townhouse'), ('officetel', 'Officetel')],
        string='Project Type', tracking=True,
    )
    segment = fields.Selection(
        [('affordable', 'Affordable'), ('mid_range', 'Mid-Range'),
         ('high_end', 'High-End'), ('luxury', 'Luxury')],
        string='Market Segment', tracking=True,
    )

    # ===== LIFECYCLE =====
    # Note: this project's *primary_state* is computed from its
    # lifecycle owners (subzones if low-rise, buildings otherwise)
    # — we do not store a single state on the project itself, since a
    # real project routinely has its component blocks in different
    # phases at the same time (e.g. tower S1 in operation while S3 is
    # still under construction).

    development_type = fields.Selection(
        [('high_rise', 'High-Rise / Chung cư'),
         ('low_rise',  'Low-Rise / BT, LK, Shophouse'),
         ('mixed',     'Mixed (high + low)')],
        string='Development Type', required=True, default='high_rise',
        tracking=True,
        help="Determines the default lifecycle granularity. "
             "High-rise projects track lifecycle per building; "
             "low-rise per subzone (a cluster of villas / townhouses "
             "is delivered together).",
    )

    lifecycle_level = fields.Selection(
        [('building', 'Per Building'),
         ('subzone',  'Per Subzone')],
        string='Lifecycle Tracked At',
        compute='_compute_lifecycle_level',
        store=True, readonly=False, tracking=True,
        help="Which entity owns the state machine. Auto-set from "
             "Development Type but overridable. Once set, transition "
             "buttons appear on subzone or building forms accordingly.",
    )

    primary_state = fields.Selection(
        # Imported lazily inside the compute to avoid circular imports
        selection=lambda self: self._get_lifecycle_states_selection(),
        string='Overall Phase',
        compute='_compute_primary_state', store=True,
        help="The most-advanced phase across the project's lifecycle "
             "owners. Used by suite filters to decide whether the "
             "project is relevant.",
    )

    # ------------------------------------------------------------------
    # Sale activity gating (Phase 4.0a)
    # ------------------------------------------------------------------
    # Independent of lifecycle state: a project can be in the `selling`
    # phase yet still NOT be open for sale activities (Booking, Reservation,
    # Direct Sales display) because management has not yet "released" it.
    # Effective gating on a Unit ANDs this flag with the equivalents on
    # Subzone (if any) and Building. See re.unit.effective_open_for_sale.
    is_open_for_sale = fields.Boolean(
        string='Open for Sale Activities',
        default=False, tracking=True,
        help='Master switch authorizing sale activities for this project. '
             'When False, units of this project are hidden from Direct '
             'Sales and no Booking / Reservation can be created.',
    )

    state_summary = fields.Char(
        string='Phase Summary',
        compute='_compute_state_summary',
        help="Short text summary of how blocks are distributed "
             "across phases, e.g. '3 selling, 2 construction, 1 operation'.",
    )

    # MASTER PLAN
    total_area_ha = fields.Float(string='Total Land Area (ha)', digits=(10, 2))
    built_area_ha = fields.Float(string='Built Area (ha)', digits=(10, 2))
    green_area_percent = fields.Float(string='Green Area (%)', digits=(5, 2))
    density_percent = fields.Float(string='Density (%)', digits=(5, 2))

    # LEGAL
    legal_status = fields.Selection(
        [('planning_approved', 'Planning Approved'),
         ('construction_permit', 'Construction Permit'),
         ('building_permit', 'Building Permit'),
         ('occupancy_permit', 'Occupancy Permit'),
         ('land_use_certificate', 'Land Use Certificate')],
        string='Legal Status', tracking=True,
    )
    legal_doc_number = fields.Char(string='Legal Document Number')
    legal_doc_date = fields.Date(string='Legal Document Date')

    # DEVELOPERS
    master_developer_id = fields.Many2one(
        'res.partner', string='Master Developer',
        domain="[('is_company', '=', True)]", tracking=True,
    )
    co_developer_ids = fields.Many2many(
        'res.partner', 'project_co_developer_rel',
        'project_id', 'partner_id',
        string='Co-Developers', domain="[('is_company', '=', True)]",
    )
    developer_id = fields.Many2one(
        'res.partner', string='Sales Developer',
        domain="[('is_company', '=', True)]", tracking=True,
    )

    # LOCATION (Vietnam top-down: Country → Province → Ward → Street)
    country_id = fields.Many2one(
        'res.country', string='Country',
        default=lambda self: self.env.ref('base.vn', raise_if_not_found=False),
    )
    state_id = fields.Many2one(
        'res.country.state', string='Province',
        domain="[('country_id', '=', country_id)]",
        tracking=True,
    )
    ward_id = fields.Many2one(
        'vau.ward', string='Ward / Phường-Xã',
        domain="[('state_id', '=', state_id)]",
    )
    street = fields.Char(string='Street', translate=True,
        help='Số nhà + tên đường')
    latitude = fields.Float(string='Latitude', digits=(10, 7))
    longitude = fields.Float(string='Longitude', digits=(10, 7))

    # DATES
    start_date = fields.Date(string='Start Date')
    expected_handover_date = fields.Date(string='Expected Handover Date')

    # MARKETING
    tagline = fields.Char(string='Tagline', translate=True)
    selling_point = fields.Text(string='Selling Points', translate=True)
    description = fields.Html(string='Description', translate=True)
    image = fields.Image(string='Project Image', max_width=1920, max_height=1080)
    masterplan_image = fields.Image(string='Masterplan', max_width=3000, max_height=3000)
    brochure_attachment_ids = fields.Many2many(
        'ir.attachment', 'project_brochure_attachment_rel',
        'project_id', 'attachment_id', string='Brochures',
    )

    # CONTACT
    sales_office_address = fields.Char(string='Sales Office Address', translate=True)
    sales_phone = fields.Char(string='Sales Hotline')
    sales_email = fields.Char(string='Sales Email')
    website_url = fields.Char(string='Website URL')

    # RELATIONS
    subzone_ids = fields.One2many('re.subzone', 'project_id', string='Subzones')
    building_ids = fields.One2many('re.building', 'project_id', string='Buildings')
    unit_ids = fields.One2many('re.unit', 'project_id', string='Units')

    subzone_count = fields.Integer(compute='_compute_counts')
    building_count = fields.Integer(compute='_compute_counts')
    floor_count = fields.Integer(compute='_compute_counts')
    unit_count = fields.Integer(compute='_compute_counts')
    available_unit_count = fields.Integer(compute='_compute_counts')

    active = fields.Boolean(default=True)

    _unique_code = models.Constraint('UNIQUE(code)', 'Project code must be unique!')

    @api.depends('subzone_ids', 'building_ids', 'unit_ids', 'unit_ids.state')
    def _compute_counts(self):
        for rec in self:
            rec.subzone_count = len(rec.subzone_ids)
            rec.building_count = len(rec.building_ids)
            rec.floor_count = sum(len(b.floor_ids) for b in rec.building_ids)
            rec.unit_count = len(rec.unit_ids)
            rec.available_unit_count = len(rec.unit_ids.filtered(lambda u: u.state == 'available'))

    @api.depends('name', 'code')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f'[{rec.code}] {rec.name}' if rec.code else rec.name

    def action_view_subzones(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Subzones', 'res_model': 're.subzone',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }

    def action_view_buildings(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Buildings', 'res_model': 're.building',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }

    def action_view_units(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Units', 'res_model': 're.unit',
            'view_mode': 'list,form,kanban',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }

    @api.onchange('country_id')
    def _onchange_country_id_clear_state(self):
        """Clear state and ward when country changes."""
        for project in self:
            if project.state_id and project.state_id.country_id != project.country_id:
                project.state_id = False
                project.ward_id = False

    @api.onchange('state_id')
    def _onchange_state_id_clear_ward(self):
        """Clear ward when state changes."""
        for project in self:
            if project.ward_id and project.ward_id.state_id != project.state_id:
                project.ward_id = False

    # ----------------------------------------------------------------------
    # Lifecycle: computes
    # ----------------------------------------------------------------------

    @staticmethod
    def _get_lifecycle_states_selection():
        """Return the LIFECYCLE_STATES list, deferred to avoid circular import.

        ``re_project`` is imported before ``_lifecycle_mixin`` only in
        edge cases, but using a lambda+staticmethod for the selection
        keeps the import flexible.
        """
        from . _lifecycle_mixin import LIFECYCLE_STATES
        return LIFECYCLE_STATES

    @api.depends('development_type')
    def _compute_lifecycle_level(self):
        """Default lifecycle_level from development_type.

        Users may override on a per-project basis (the field is
        ``readonly=False`` despite being computed). Mixed defaults
        to building because high-rise components are usually the
        bulk and certainly the more state-driven ones.
        """
        for rec in self:
            # Don't overwrite a manual choice
            if rec.lifecycle_level:
                continue
            rec.lifecycle_level = (
                'subzone' if rec.development_type == 'low_rise' else 'building'
            )

    @api.depends('lifecycle_level',
                 'subzone_ids.state', 'building_ids.state')
    def _compute_primary_state(self):
        """The "farthest along" state across active lifecycle owners.

        With heterogeneous projects (5 buildings each in a different
        phase) a single state is necessarily a lossy summary; we pick
        the latest-along-lifecycle one as a proxy "where is the
        project mostly at?". The full distribution is in
        :attr:`state_summary`.
        """
        from ._lifecycle_mixin import STATE_ORDER
        for rec in self:
            owners = (rec.subzone_ids
                      if rec.lifecycle_level == 'subzone'
                      else rec.building_ids)
            if not owners:
                rec.primary_state = 'planning'
                continue
            states = owners.mapped('state')
            # Pick the state with the largest STATE_ORDER index
            rec.primary_state = max(
                states, key=lambda s: STATE_ORDER.index(s)
            )

    @api.depends('lifecycle_level',
                 'subzone_ids.state', 'building_ids.state')
    def _compute_state_summary(self):
        """Human-readable distribution of states across owners.

        Example outputs:
          - "3 selling, 2 construction"
          - "1 operation, 4 product_handover, 2 construction"
          - "" (empty if there are no owners yet)
        """
        from collections import Counter
        for rec in self:
            owners = (rec.subzone_ids
                      if rec.lifecycle_level == 'subzone'
                      else rec.building_ids)
            if not owners:
                rec.state_summary = ''
                continue
            counts = Counter(owners.mapped('state'))
            rec.state_summary = ', '.join(
                f'{n} {state}' for state, n in counts.most_common()
            )
