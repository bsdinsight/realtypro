# -*- coding: utf-8 -*-
"""rp.tender.package — Gói thầu (Phase 2 v1.4.1 basic version).

A Gói thầu (tender package) groups multiple Hạng mục dự án together
for procurement. Example: a "MEP Package" might cover MEP work across
3 towers in 2 different subzones.

Phase 2 v1.4.1 ships:
- Header: name, code, project, currency, estimated_amount, scope,
  subzone filter (UX), contractor link (optional), state machine
- Lines: each line points to one rp.structure (Hạng mục or Sub-hạng mục)
- Constraint: each Hạng mục can only appear once per package

Phase 5 will _inherit and add:
- Replace simple contractor_id with award workflow (bidder_ids,
  awarded_contractor_id, award_date, award_amount)
- Stronger state machine: draft → issued → bidding → awarded → closed
- Linked contracts: contract_ids O2M rp.contract
- Budget linkage: which cost.plan.line each tender amount draws from
"""

from odoo import api, fields, models
from odoo.exceptions import ValidationError, UserError


class RpTenderPackage(models.Model):
    _name = 'rp.tender.package'
    _description = 'Tender Package / Gói thầu'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'project_id, sequence, code, id desc'

    # ----- Identity
    name = fields.Char(
        string='Tên gói thầu',
        required=True, translate=True, tracking=True,
    )
    code = fields.Char(string='Mã gói thầu', tracking=True)
    sequence = fields.Integer(default=10)

    # ----- Project anchor
    project_id = fields.Many2one(
        're.project', string='Dự án',
        required=True, ondelete='restrict', index=True, tracking=True,
    )

    # ----- Subzone filter (UX convenience, NOT a hard constraint)
    subzone_filter_id = fields.Many2one(
        're.subzone', string='Lọc theo khu vực',
        domain="[('project_id', '=', project_id)]",
        help='UX convenience: when set, the Hạng mục picker on new '
             'lines filters to structures in this subzone. The package '
             'itself can still span multiple subzones — this is just '
             'a quick-add filter.',
    )

    # ----- Contractor link (chuẩn Odoo: res.partner)
    contractor_id = fields.Many2one(
        'res.partner', string='Nhà thầu',
        ondelete='set null', tracking=True,
        domain="[('is_company', '=', True)]",
        help='Awarded contractor — chuẩn Odoo dùng res.partner. '
             'Dropdown hiển thị tất cả công ty; pick lần đầu sẽ '
             'auto-flag is_contractor=True trên partner.',
    )

    # ----- Scope
    scope_summary = fields.Text(
        string='Phạm vi gói thầu',
        help='Free-text description of what the package covers. Used '
             'in RFP / RFQ documents.',
    )
    estimated_amount = fields.Monetary(
        string='Giá trị ước tính',
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        'res.currency', string='Currency',
        required=True, default=lambda self: self.env.company.currency_id,
    )

    # ----- Lines
    line_ids = fields.One2many(
        'rp.tender.package.line', 'package_id',
        string='Hạng mục in Package', copy=True,
    )
    line_count = fields.Integer(compute='_compute_line_count', store=True)
    subzone_coverage = fields.Char(
        compute='_compute_subzone_coverage', store=True,
        help='Comma-separated subzones covered by the package lines.',
    )

    # ----- State (Phase 2 lightweight)
    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('active', 'Active'),
            ('closed', 'Closed'),
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

    # ===== Onchange — auto-flag contractor =====

    @api.onchange('contractor_id')
    def _onchange_contractor_flag(self):
        if self.contractor_id and not self.contractor_id.is_contractor:
            self.contractor_id.is_contractor = True

    # ===== Computeds =====

    @api.depends('line_ids')
    def _compute_line_count(self):
        for pkg in self:
            pkg.line_count = len(pkg.line_ids)

    @api.depends('line_ids.subzone_id')
    def _compute_subzone_coverage(self):
        for pkg in self:
            subzones = pkg.line_ids.mapped('subzone_id')
            if not subzones:
                pkg.subzone_coverage = ''
                continue
            names = sorted(set(sz.name for sz in subzones if sz))
            if names:
                pkg.subzone_coverage = ', '.join(names)
            else:
                pkg.subzone_coverage = 'Common Cost only'

    # ===== Constraints =====

    def init(self):
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS rp_tender_package_unique_code_per_project
            ON rp_tender_package (project_id, code)
            WHERE code IS NOT NULL
        """)

    @api.constrains('contractor_id', 'company_id')
    def _check_contractor_company(self):
        for pkg in self:
            if pkg.contractor_id and pkg.contractor_id.company_id != pkg.company_id:
                raise ValidationError(
                    'Nhà thầu phải cùng company với gói thầu.'
                )

    # ===== State transitions =====

    def action_activate(self):
        for pkg in self:
            if pkg.state != 'draft':
                continue
            if not pkg.line_ids:
                raise UserError(
                    'Không thể activate gói thầu không có Hạng mục nào.'
                )
            pkg.state = 'active'

    def action_close(self):
        for pkg in self:
            if pkg.state != 'active':
                continue
            pkg.state = 'closed'

    def action_reset_to_draft(self):
        if not self.env.user.has_group('re_base.group_re_manager'):
            raise UserError('Chỉ manager mới được reset state.')
        for pkg in self:
            pkg.state = 'draft'


class RpTenderPackageLine(models.Model):
    _name = 'rp.tender.package.line'
    _description = 'Tender Package Line'
    _order = 'package_id, sequence, id'

    package_id = fields.Many2one(
        'rp.tender.package', string='Gói thầu',
        required=True, ondelete='cascade', index=True,
    )
    project_id = fields.Many2one(
        related='package_id.project_id', store=True, index=True,
    )
    currency_id = fields.Many2one(
        related='package_id.currency_id', store=True,
    )

    sequence = fields.Integer(default=10)
    name = fields.Char(
        string='Mô tả',
        translate=True,
        help='Optional override. If empty, displays structure name.',
    )

    # ----- Anchor
    structure_id = fields.Many2one(
        'rp.structure', string='Hạng mục',
        required=True, ondelete='restrict', index=True,
    )
    subzone_id = fields.Many2one(
        're.subzone', string='Khu vực',
        related='structure_id.subzone_id', store=True, index=True, readonly=True,
    )
    structure_level = fields.Selection(
        related='structure_id.structure_level', store=True, readonly=True,
    )
    structure_type = fields.Selection(
        related='structure_id.structure_type', store=True, readonly=True,
    )

    # ----- Amount
    estimated_amount = fields.Monetary(
        string='Giá trị ước tính',
        currency_field='currency_id',
    )

    # ----- Note
    scope_note = fields.Text(string='Ghi chú phạm vi')

    # ===== Constraints =====

    @api.constrains('structure_id', 'package_id')
    def _check_structure_same_project(self):
        for line in self:
            if line.structure_id.project_id != line.package_id.project_id:
                raise ValidationError(
                    'Hạng mục phải cùng dự án với gói thầu.'
                )

    _unique_structure_per_package = models.Constraint(
        'UNIQUE(package_id, structure_id)',
        'Mỗi Hạng mục chỉ có thể xuất hiện một lần trong gói thầu.',
    )
