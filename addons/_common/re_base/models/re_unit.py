from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


DIRECTION_SELECTION = [
    ('n', 'North (Bắc)'), ('ne', 'Northeast (Đông Bắc)'),
    ('e', 'East (Đông)'), ('se', 'Southeast (Đông Nam)'),
    ('s', 'South (Nam)'), ('sw', 'Southwest (Tây Nam)'),
    ('w', 'West (Tây)'), ('nw', 'Northwest (Tây Bắc)'),
]

VIEW_SELECTION = [
    ('lake', 'Lake View'), ('river', 'River View'),
    ('sea', 'Sea View'), ('mountain', 'Mountain View'),
    ('city', 'City View'), ('park', 'Park View'),
    ('pool', 'Pool View'), ('internal', 'Internal View'),
    ('garden', 'Garden View'), ('other', 'Other'),
]

POSITION_ON_FLOOR_SELECTION = [
    ('corner', 'Corner Unit'), ('front', 'Front-Facing'),
    ('side', 'Side'), ('inner', 'Inner'), ('back', 'Back'),
]


class ReUnit(models.Model):
    _name = 're.unit'
    _description = 'Real Estate Unit'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'project_id, building_id, floor_id, unit_code'
    _rec_name = 'unit_code'

    unit_code = fields.Char(string='Unit Code', required=True, tracking=True, copy=False)

    project_id = fields.Many2one('re.project', string='Project', required=True,
                                  tracking=True, ondelete='restrict')
    subzone_id = fields.Many2one(related='building_id.subzone_id', store=True, string='Subzone')
    building_id = fields.Many2one('re.building', string='Building', required=True,
                                   tracking=True, ondelete='restrict',
                                   domain="[('project_id', '=', project_id)]")
    floor_id = fields.Many2one('re.floor', string='Floor', required=True,
                                tracking=True, ondelete='restrict',
                                domain="[('building_id', '=', building_id)]")

    unit_type_id = fields.Many2one('re.unit.type', string='Unit Type', required=True, tracking=True)

    # ----- Area: planned (set when unit is created) -----
    # Three Vietnamese real-estate area concepts. Used at sales time.
    area_gross = fields.Float(
        string='Gross Area (Tim tường, m²)', digits=(10, 2), tracking=True,
        help="Diện tích tim tường: includes walls. Larger of the three.",
    )
    area_net = fields.Float(
        string='Net Area (Thông thuỷ, m²)', digits=(10, 2), tracking=True,
        help="Diện tích thông thuỷ: usable interior, excludes walls. "
             "Must be ≤ gross area.",
    )
    area_sellable = fields.Float(
        string='Sellable Area (Sử dụng, m²)', digits=(10, 2), tracking=True,
        help="Diện tích sử dụng: the area written on the sale contract "
             "(HĐMB). Defined by Vietnamese regulation; can differ from "
             "both gross and net depending on developer policy.",
    )

    # ----- Area: actual (measured at handover) -----
    # Same three concepts but measured after construction. Variance vs.
    # planned can trigger price adjustment per the sale contract terms.
    area_gross_actual = fields.Float(
        string='Gross Area Actual (m²)', digits=(10, 2), tracking=True,
        help="Tim tường thực tế: measured at handover.",
    )
    area_net_actual = fields.Float(
        string='Net Area Actual (m²)', digits=(10, 2), tracking=True,
        help="Thông thuỷ thực tế: measured at handover.",
    )
    area_sellable_actual = fields.Float(
        string='Sellable Area Actual (m²)', digits=(10, 2), tracking=True,
        help="Sử dụng thực tế: measured at handover. May trigger price "
             "rebate/charge if it differs from area_sellable on HĐMB.",
    )

    direction = fields.Selection(DIRECTION_SELECTION, string='Direction', tracking=True)
    view_type = fields.Selection(VIEW_SELECTION, string='View', tracking=True)
    bedroom_count = fields.Integer(string='Bedrooms', tracking=True)
    bathroom_count = fields.Integer(string='Bathrooms', tracking=True)
    balcony_count = fields.Integer(string='Balconies')

    area_balcony = fields.Float(string='Balcony Area (m²)', digits=(10, 2))
    area_garden = fields.Float(string='Garden Area (m²)', digits=(10, 2))
    area_terrace = fields.Float(string='Terrace Area (m²)', digits=(10, 2))
    area_parking = fields.Float(string='Parking Area (m²)', digits=(10, 2))

    legal_doc_type = fields.Selection(
        [('hop_dong_mua_ban', 'Sale Contract (HĐMB)'),
         ('so_hong', 'Pink Book (Sổ hồng)'),
         ('so_do', 'Red Book (Sổ đỏ)'),
         ('chua_co', 'Not Yet Issued')],
        string='Legal Document Type', tracking=True,
    )
    red_book_number = fields.Char(string='Red/Pink Book Number')
    red_book_issue_date = fields.Date(string='Book Issue Date')
    land_use_type = fields.Selection(
        [('lau_dai', 'Permanent (Sở hữu lâu dài)'),
         ('50_nam', '50 Years'), ('70_nam', '70 Years')],
        string='Land Use Type',
    )

    interior_status = fields.Selection(
        [('raw', 'Raw / Bare Shell'), ('basic_finish', 'Basic Finishing'),
         ('fully_furnished', 'Fully Furnished'),
         ('luxury_furnished', 'Luxury Furnished')],
        string='Interior Status', tracking=True,
    )
    furniture_brand = fields.Char(string='Furniture Brand')

    parking_slot_count = fields.Integer(string='Car Parking Slots', default=0)
    motorbike_slot_count = fields.Integer(string='Motorbike Slots', default=0)
    storage_room = fields.Boolean(string='Storage Room')
    storage_area = fields.Float(string='Storage Area (m²)', digits=(10, 2))

    position_on_floor = fields.Selection(POSITION_ON_FLOOR_SELECTION, string='Position on Floor')
    unit_number_on_floor = fields.Char(string='Unit Number on Floor')

    original_price = fields.Monetary(string='Original Price (excl. VAT)',
        currency_field='currency_id', tracking=True)
    price_per_m2 = fields.Monetary(string='Price per m²',
        currency_field='currency_id', compute='_compute_price_per_m2', store=True)
    vat_rate = fields.Float(string='VAT Rate (%)', default=10.0)
    maintenance_fee_rate = fields.Float(string='Maintenance Fee Rate (%)', default=2.0)
    vat_amount = fields.Monetary(string='VAT Amount',
        currency_field='currency_id', compute='_compute_pricing_breakdown', store=True)
    maintenance_fee_amount = fields.Monetary(string='Maintenance Fee Amount',
        currency_field='currency_id', compute='_compute_pricing_breakdown', store=True)
    total_price = fields.Monetary(string='Total Price (incl. VAT + Maintenance)',
        currency_field='currency_id', compute='_compute_pricing_breakdown', store=True)
    currency_id = fields.Many2one('res.currency', string='Currency',
        default=lambda self: self.env.ref('base.VND', raise_if_not_found=False)
        or self.env.company.currency_id)

    marketing_description = fields.Html(string='Marketing Description', translate=True)
    selling_point = fields.Text(string='Selling Points (USP)', translate=True)
    is_featured = fields.Boolean(string='Featured Unit')
    is_premium = fields.Boolean(string='Premium Unit')

    # ------------------------------------------------------------------
    # Sale activity gating — effective rollup (Phase 4.0a)
    # ------------------------------------------------------------------
    # True iff sale activities are authorized at every level above this
    # unit. Direct Sales / Booking / Reservation backends consult this
    # field rather than the individual flags. Stored so the search at
    # /api/units/search can filter with a SQL index.
    effective_open_for_sale = fields.Boolean(
        string='Open for Sale (effective)',
        compute='_compute_effective_open_for_sale',
        store=True,
        help='True only when the project, subzone (if any) and building '
             'are all flagged "Open for Sale Activities". Determines '
             'whether the unit appears on Direct Sales and accepts '
             'Booking / Reservation creation.',
    )

    state = fields.Selection(
        [('draft', 'Draft'), ('available', 'Available'),
         ('on_hold', 'On Hold'), ('booked', 'Booked'),
         ('deposited', 'Deposited'), ('contracted', 'Contracted'),
         ('handed_over', 'Handed Over'), ('locked', 'Locked'),
         ('cancelled', 'Cancelled')],
        string='Status', default='draft', tracking=True, required=True,
    )

    # ----- Handover -----
    # Vietnamese real-estate splits handover into TWO distinct events:
    #
    #   1. Product handover (bàn giao nhà): keys handed to the buyer,
    #      they can move in and decorate. Operations (Living suite)
    #      starts caring about the unit from this point.
    #
    #   2. Certificate handover (bàn giao sổ): the legal title (sổ hồng
    #      / sổ đỏ) is issued by Sở TN&MT and handed to the owner. Often
    #      6 months to 2-3 years AFTER product handover. Sales suite
    #      keeps the buyer relationship alive until this happens.
    expected_handover_date = fields.Date(
        string='Expected Handover Date', tracking=True,
        help="Planned product handover date — when keys will be given.",
    )
    product_handover_date = fields.Date(
        string='Product Handover Date', tracking=True,
        help="Actual date keys were handed over (bàn giao nhà). "
             "Resident may move in from this date.",
    )
    certificate_handover_date = fields.Date(
        string='Certificate Handover Date', tracking=True,
        help="Date the title certificate (sổ hồng / sổ đỏ) was issued "
             "to the owner. Routinely months to years after product "
             "handover in Vietnam.",
    )
    certificate_number = fields.Char(
        string='Certificate Number', tracking=True,
        help="Số sổ hồng / sổ đỏ issued by Sở TN&MT.",
    )
    handover_condition = fields.Selection(
        [('on_schedule', 'On Schedule'), ('delayed', 'Delayed'),
         ('advanced', 'Advanced (Earlier)')],
        string='Handover Condition',
        help="Whether product handover happened on, before, or after "
             "the expected date.",
    )
    handover_notes = fields.Text(string='Handover Notes')

    locked_by = fields.Many2one('res.users', string='Locked By', readonly=True, copy=False)
    locked_until = fields.Datetime(string='Locked Until', readonly=True, copy=False)
    version = fields.Integer(string='Version', default=1, readonly=True, copy=False)

    image = fields.Image(string='Unit Image', max_width=1920, max_height=1080)
    layout_image = fields.Image(string='Floor Plan', max_width=2400, max_height=2400)
    notes = fields.Text(string='Internal Notes')

    active = fields.Boolean(default=True)

    _unique_unit_code_per_project = models.Constraint(
        'UNIQUE(project_id, unit_code)',
        'Unit code must be unique within a project!',
    )

    @api.constrains('area_gross', 'area_net', 'area_sellable',
                    'area_gross_actual', 'area_net_actual', 'area_sellable_actual')
    def _check_areas(self):
        """Areas must be non-negative; net ≤ gross when both provided.

        Sellable area is intentionally not constrained against the
        other two: Vietnamese regulation lets developers compute it
        differently (e.g. carpet + 50% of shared corridor share), so
        a sellable > net or sellable > gross is legitimately possible.
        """
        for rec in self:
            for f in ('area_gross', 'area_net', 'area_sellable',
                      'area_gross_actual', 'area_net_actual', 'area_sellable_actual'):
                v = getattr(rec, f)
                if v and v < 0:
                    raise ValidationError(_('Area %s must be non-negative.', f))
            if rec.area_net and rec.area_gross and rec.area_net > rec.area_gross:
                raise ValidationError(_(
                    'Net area cannot be greater than gross area.\n'
                    'Unit %(code)s: net=%(net).2f m², gross=%(gross).2f m²',
                    code=rec.unit_code, net=rec.area_net, gross=rec.area_gross,
                ))
            if (rec.area_net_actual and rec.area_gross_actual
                    and rec.area_net_actual > rec.area_gross_actual):
                raise ValidationError(_(
                    'Net area (actual) cannot be greater than gross area (actual).\n'
                    'Unit %(code)s: net_actual=%(net).2f m², gross_actual=%(gross).2f m²',
                    code=rec.unit_code,
                    net=rec.area_net_actual, gross=rec.area_gross_actual,
                ))

    @api.onchange('area_gross', 'area_net')
    def _onchange_area_remind_sellable(self):
        """Nudge the user to fill area_sellable once they've set the others.

        ``area_sellable`` is the area that goes on the HĐMB (sale
        contract) and is defined separately by Vietnamese regulation —
        we can't compute it for them. Showing a non-blocking warning
        when they enter the other two areas without sellable is the
        smallest UX prod we can do without breaking the form.
        """
        for rec in self:
            if (rec.area_gross or rec.area_net) and not rec.area_sellable:
                return {
                    'warning': {
                        'title': _('Sellable Area not set'),
                        'message': _(
                            "You've entered gross or net area but left "
                            "Sellable Area (Diện tích sử dụng) blank. "
                            "This is the area that will appear on the "
                            "sale contract (HĐMB) — please fill it in "
                            "before activating the unit."
                        ),
                    }
                }

    @api.depends('original_price', 'area_net')
    def _compute_price_per_m2(self):
        """Price per m² is computed against NET area (thông thuỷ).

        This is the most common Vietnamese real-estate convention for
        listing prices; if a project policy uses gross or sellable,
        downstream sale-program logic overrides this with explicit
        unit_price_gross / unit_price_net columns on the price list.
        """
        for rec in self:
            rec.price_per_m2 = (rec.original_price / rec.area_net) if rec.area_net else 0.0

    @api.depends('original_price', 'vat_rate', 'maintenance_fee_rate')
    def _compute_pricing_breakdown(self):
        for rec in self:
            rec.vat_amount = rec.original_price * (rec.vat_rate or 0) / 100
            rec.maintenance_fee_amount = rec.original_price * (rec.maintenance_fee_rate or 0) / 100
            rec.total_price = rec.original_price + rec.vat_amount + rec.maintenance_fee_amount

    @api.depends('unit_code', 'project_id.code')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.unit_code or _('New Unit')

    @api.depends('project_id.is_open_for_sale',
                 'subzone_id.is_open_for_sale',
                 'building_id.is_open_for_sale')
    def _compute_effective_open_for_sale(self):
        """Rollup of the three is_open_for_sale flags above this unit.

        Subzone is optional — if a unit has no subzone (because the
        project does not use subzones), only project and building gate
        the result.
        """
        for rec in self:
            if not rec.project_id or not rec.building_id:
                rec.effective_open_for_sale = False
                continue
            ok = rec.project_id.is_open_for_sale and rec.building_id.is_open_for_sale
            if rec.subzone_id:
                ok = ok and rec.subzone_id.is_open_for_sale
            rec.effective_open_for_sale = ok

    @api.onchange('project_id')
    def _onchange_project_id(self):
        if self.building_id and self.building_id.project_id != self.project_id:
            self.building_id = False
            self.floor_id = False

    @api.onchange('building_id')
    def _onchange_building_id(self):
        if self.floor_id and self.floor_id.building_id != self.building_id:
            self.floor_id = False

    @api.onchange('unit_type_id')
    def _onchange_unit_type_id(self):
        if self.unit_type_id:
            ut = self.unit_type_id
            if not self.bedroom_count:
                self.bedroom_count = ut.default_bedroom_count
            if not self.bathroom_count:
                self.bathroom_count = ut.default_bathroom_count
            if not self.balcony_count:
                self.balcony_count = ut.default_balcony_count
            if not self.view_type and ut.default_view_type:
                self.view_type = ut.default_view_type

    def action_set_available(self):
        for rec in self:
            if rec.state in ('booked', 'deposited', 'contracted', 'handed_over'):
                raise ValidationError(_(
                    'Cannot set unit %s back to Available - it is already %s.'
                ) % (rec.unit_code, rec.state))
            rec.state = 'available'
            rec.locked_by = False
            rec.locked_until = False

    def action_lock(self):
        self.write({'state': 'locked'})

    def action_unlock(self):
        for rec in self:
            if rec.state == 'locked':
                rec.state = 'available'

    def action_cancel(self):
        self.write({'state': 'cancelled'})
