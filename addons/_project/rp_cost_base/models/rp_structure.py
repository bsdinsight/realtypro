# -*- coding: utf-8 -*-
"""rp.structure — Hạng mục dự án (Project Structure) v1.4.3-r4.

Two structure_level values:

- ``item`` (Hạng mục dự án): top-level work item within a subzone.
  Examples: "Tower S1.01", "Hotel Tower H1", "Sân golf 18 hố".
- ``sub_item`` (Sub-hạng mục): subdivision of an item. Optional.
  Examples: under "Tower S1.01", you might have "Tầng hầm",
  "Phần thân tầng 1-32", "Tầng 33-40 penhouse", "Trung tâm thương mại".

**v1.4.3-r4 changes from v1.4.2**:
- Removed ``common_cost`` value from structure_level. Common-pool costs
  are now modeled as a regular cost category line on whichever
  structure is most appropriate. No more auto-placeholder.
- Removed ``building_id`` field. Building/Floor information is captured
  elsewhere (re.building, re.floor on re_base). If a phase later needs
  to reference building from structure, it can _inherit and add the
  field cleanly.
- Removed helper ``_get_or_create_common_cost``.
- Removed ``is_common_cost`` computed flag (no longer meaningful).

**Cost entry (Khái toán)**:
Each structure carries a list of ``rp.structure.estimate.line``
records — one per cost category — via O2M ``estimate_line_ids``.
Computed ``estimate_total`` sums them up. This is the primary
data-entry surface for Khái toán in Phase 2.

Constraints:
- ``item`` must have subzone_id, no parent_id.
- ``sub_item`` must have parent_id (of level=item), subzone inherited
  from parent.
"""

from odoo import api, fields, models
from odoo.exceptions import ValidationError


STRUCTURE_LEVELS = [
    ('item', 'Hạng mục / Item'),
    ('sub_item', 'Sub-hạng mục / Sub-item'),
]


STRUCTURE_TYPES = [
    # Residential
    ('tower', 'Residential Tower / Tháp căn hộ'),
    ('villa_block', 'Villa Block / Cụm biệt thự'),
    ('townhouse_block', 'Townhouse Block / Cụm nhà phố'),
    # Mixed use & commercial
    ('hotel', 'Hotel / Khách sạn'),
    ('hospital', 'Hospital / Bệnh viện'),
    ('office', 'Office Building / Tòa văn phòng'),
    ('commercial_center', 'Commercial Center / Trung tâm thương mại'),
    ('theatre', 'Theatre / Nhà hát'),
    ('clubhouse', 'Clubhouse'),
    # Recreation & special
    ('golf', 'Golf Course / Sân golf'),
    ('marina', 'Marina / Bến du thuyền'),
    ('port', 'Port / Cảng biển'),
    # Public realm
    ('landscape', 'Landscape / Cảnh quan'),
    ('infrastructure', 'Infrastructure / Hạ tầng kỹ thuật'),
    ('road', 'Road / Đường giao thông'),
    ('bridge', 'Bridge / Cầu'),
    ('utility', 'Utility / Trạm điện-nước-xử lý'),
    # Sub-item granularity
    ('foundation', 'Foundation / Móng-cọc'),
    ('basement', 'Basement / Tầng hầm'),
    ('structure_body', 'Structure Body / Phần thân'),
    ('facade', 'Facade / Mặt dựng'),
    ('mep', 'MEP'),
    ('interior', 'Interior Fit-out / Nội thất'),
    # Catch-all
    ('other', 'Other / Khác'),
]


class RpStructure(models.Model):
    _name = 'rp.structure'
    _description = 'Project Structure / Hạng mục dự án'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'project_id, subzone_id, sequence, code, name'
    _parent_store = True
    _parent_name = 'parent_id'

    # ----- Identity
    name = fields.Char(string='Name', required=True, translate=True, tracking=True)
    code = fields.Char(string='Code', tracking=True)
    sequence = fields.Integer(default=10)

    # ----- Level & type
    structure_level = fields.Selection(
        STRUCTURE_LEVELS, string='Level',
        required=True, default='item', tracking=True,
    )
    structure_type = fields.Selection(
        STRUCTURE_TYPES, string='Type',
        required=True, default='tower', tracking=True,
    )

    # ----- Hierarchy
    project_id = fields.Many2one(
        're.project', string='Project',
        required=True, ondelete='cascade', index=True, tracking=True,
    )
    subzone_id = fields.Many2one(
        're.subzone', string='Subzone / Phân khu',
        required=True, ondelete='restrict', index=True, tracking=True,
        domain="[('project_id', '=', project_id)]",
        help='Required for both item and sub_item. Sub_item inherits '
             'from its parent automatically.',
    )
    parent_id = fields.Many2one(
        'rp.structure', string='Parent / Hạng mục cha',
        index=True, ondelete='restrict', tracking=True,
        domain="[('project_id', '=', project_id), "
               "('structure_level', '=', 'item'), "
               "('id', '!=', id)]",
        help='Required for sub_item (must point to an item structure); '
             'forbidden for item.',
    )
    child_ids = fields.One2many(
        'rp.structure', 'parent_id',
        string='Sub-items',
    )
    parent_path = fields.Char(index=True)

    # ----- Planning figures
    planned_gfa = fields.Float(
        string='Planned GFA (m²)',
        help='Gross floor area for planning purposes.',
    )
    planned_area_sqm = fields.Float(
        string='Planned Land Area (m²)',
        help='Land footprint, for landscape/road/infrastructure items.',
    )
    planned_units = fields.Integer(
        string='Planned Units',
        help='Number of dwelling units (residential) or rooms (hotel).',
    )
    planned_floors = fields.Integer(
        string='Planned Floors',
        help='Number of floors above ground.',
    )
    planned_basement_levels = fields.Integer(
        string='Planned Basement Levels',
    )
    planned_road_length_m = fields.Float(
        string='Planned Road Length (m)',
        help='For road / bridge structures.',
    )

    # ----- Estimate (Khái toán) inline lines
    estimate_line_ids = fields.One2many(
        'rp.structure.estimate.line', 'structure_id',
        string='Khái toán', copy=True,
    )
    estimate_total = fields.Monetary(
        string='Tổng Khái toán',
        compute='_compute_estimate_total', store=True,
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        'res.currency', string='Currency',
        default=lambda self: self.env.company.currency_id,
    )

    # ----- State machine (lightweight)
    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('confirmed', 'Confirmed'),
            ('archived', 'Archived'),
        ],
        string='State', default='draft', required=True,
        tracking=True, readonly=True, copy=False,
    )

    # ----- Misc
    description = fields.Text()
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', string='Company',
        default=lambda self: self.env.company,
    )

    # ===== Computeds =====

    @api.depends('estimate_line_ids.amount')
    def _compute_estimate_total(self):
        for rec in self:
            rec.estimate_total = sum(
                line.amount for line in rec.estimate_line_ids
            )

    # ===== Onchange (UX) =====

    @api.onchange('parent_id')
    def _onchange_parent_inherits_subzone(self):
        """When user picks a parent (sub_item flow), inherit subzone."""
        for rec in self:
            if rec.structure_level == 'sub_item' and rec.parent_id:
                rec.subzone_id = rec.parent_id.subzone_id

    @api.onchange('structure_level')
    def _onchange_level_clear_parent(self):
        """Switching from sub_item back to item clears the parent."""
        for rec in self:
            if rec.structure_level == 'item' and rec.parent_id:
                rec.parent_id = False

    # ===== Constraints =====

    @api.constrains('structure_level', 'subzone_id', 'parent_id', 'project_id')
    def _check_hierarchy_invariants(self):
        for rec in self:
            if rec.structure_level == 'item':
                if not rec.subzone_id:
                    raise ValidationError(
                        f'[{rec.display_name}] An "item" structure '
                        'must have a subzone.'
                    )
                if rec.parent_id:
                    raise ValidationError(
                        f'[{rec.display_name}] An "item" structure '
                        'cannot have a parent.'
                    )
            elif rec.structure_level == 'sub_item':
                if not rec.parent_id:
                    raise ValidationError(
                        f'[{rec.display_name}] A "sub_item" must have '
                        'a parent (an item structure).'
                    )
                if rec.parent_id.structure_level != 'item':
                    raise ValidationError(
                        f'[{rec.display_name}] A "sub_item" parent '
                        'must be an "item" (not a sub_item).'
                    )
                if not rec.subzone_id:
                    raise ValidationError(
                        f'[{rec.display_name}] A "sub_item" must have '
                        'a subzone (inherits from parent).'
                    )
                if rec.subzone_id != rec.parent_id.subzone_id:
                    raise ValidationError(
                        f'[{rec.display_name}] A "sub_item"\'s subzone '
                        'must match its parent\'s subzone.'
                    )

    @api.constrains('subzone_id', 'project_id')
    def _check_subzone_same_project(self):
        for rec in self:
            if rec.subzone_id and rec.subzone_id.project_id != rec.project_id:
                raise ValidationError(
                    f'[{rec.display_name}] Subzone must belong to the '
                    'same project as the structure.'
                )

    @api.constrains('parent_id')
    def _check_no_cycle(self):
        if self._has_cycle():
            raise ValidationError(
                'Structures cannot form a circular hierarchy.'
            )

    # Postgres-level: code unique per project when code is set
    def init(self):
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS rp_structure_unique_code_per_project
            ON rp_structure (project_id, code)
            WHERE code IS NOT NULL
        """)

    # ===== State transitions =====

    def action_confirm(self):
        for rec in self:
            if rec.state != 'draft':
                continue
            rec.state = 'confirmed'

    def action_reset_to_draft(self):
        for rec in self:
            rec.state = 'draft'

    def action_archive_structure(self):
        for rec in self:
            rec.state = 'archived'
            rec.active = False

    # ===== Display tweak =====

    @api.depends('name', 'code', 'subzone_id')
    def _compute_display_name(self):
        for rec in self:
            parts = []
            if rec.code:
                parts.append(f'[{rec.code}]')
            parts.append(rec.name or '')
            if rec.subzone_id:
                parts.append(f'({rec.subzone_id.name})')
            rec.display_name = ' '.join(parts).strip()
