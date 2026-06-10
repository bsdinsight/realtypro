# -*- coding: utf-8 -*-
"""rp.contractor — Nhà thầu (contractor master data).

Phase 2 v1.4.1: full model with 3 field groups:
- Identity & Vietnam legal (tax code, business license)
- Construction capability (construction license + class + specialties)
- Project relationship & lifecycle (state machine)

Phase 5 will _inherit to add:
- Performance KPI tracking
- Insurance certificate management
- Awarding workflow integration with rp.tender.package
- Contract linkage

Phase 2 state machine:
  prospect → approved → suspended ⇄ approved → blacklisted
"""

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


CONTRACTOR_TYPES = [
    ('general', 'Tổng thầu / General Contractor'),
    ('subcontractor', 'Nhà thầu phụ / Subcontractor'),
    ('supplier', 'Nhà cung cấp / Supplier'),
    ('consultant', 'Tư vấn / Consultant'),
]

LICENSE_CLASSES = [
    ('hang_1', 'Hạng 1'),
    ('hang_2', 'Hạng 2'),
    ('hang_3', 'Hạng 3'),
    ('none', 'Không có / N/A'),
]

STATES = [
    ('prospect', 'Prospect / Đang xem xét'),
    ('approved', 'Approved / Đã phê duyệt'),
    ('suspended', 'Suspended / Tạm ngưng'),
    ('blacklisted', 'Blacklisted / Đưa vào danh sách đen'),
]


class RpContractor(models.Model):
    _name = 'rp.contractor'
    _description = 'Contractor / Nhà thầu'
    _inherits = {'res.partner': 'partner_id'}
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'state'

    # ===== Delegation pattern =====
    # rp.contractor IS-A res.partner via partner_id (1:1, required).
    # Khi tạo rp.contractor, Odoo auto-create res.partner. Mọi field
    # của res.partner truy cập trực tiếp trên rp.contractor (name,
    # phone, email, ...). Giải pháp "1 bảng" cho cả Quản lý vay và
    # Realty Project — mỗi nhà thầu chỉ tồn tại 1 record duy nhất.
    partner_id = fields.Many2one(
        'res.partner', string='Contact / res.partner',
        required=True, ondelete='restrict', auto_join=True,
        help='Auto-created khi tạo nhà thầu. Đại diện cho NT trong '
             'mọi nghiệp vụ kế toán (hóa đơn, thanh toán, TK NH).',
    )
    code = fields.Char(
        string='Mã nội bộ',
        tracking=True,
        help='Internal code (e.g. NT001). Unique within company.',
    )
    tax_code = fields.Char(
        string='Mã số thuế',
        help='Vietnam tax number — typically 10 digits for organizations '
             'or 13 digits for branches/units.',
    )
    business_license_number = fields.Char(
        string='Số giấy phép kinh doanh',
    )
    business_license_date = fields.Date(
        string='Ngày cấp GPKD',
    )
    headquarters_address = fields.Text(
        string='Địa chỉ trụ sở chính',
    )

    # ===== Group 2: Construction capability =====

    construction_license_number = fields.Char(
        string='Số chứng chỉ năng lực xây dựng',
        help='Chứng chỉ năng lực hoạt động xây dựng — required for '
             'general contractors per Vietnam construction law.',
    )
    construction_license_class = fields.Selection(
        LICENSE_CLASSES,
        string='Phân hạng năng lực',
        default='none',
        help='Hạng 1: dự án nhóm A. Hạng 2: dự án nhóm B. '
             'Hạng 3: dự án nhóm C. Theo Nghị định số 15/2021/NĐ-CP.',
    )
    construction_license_expiry = fields.Date(
        string='Ngày hết hạn chứng chỉ',
    )
    construction_license_expired = fields.Boolean(
        compute='_compute_license_expired', store=True,
        string='License Expired',
        help='True if construction_license_expiry is in the past.',
    )
    specialty_ids = fields.Many2many(
        'rp.contractor.specialty',
        'rp_contractor_specialty_rel',
        'contractor_id', 'specialty_id',
        string='Chuyên môn',
    )
    contractor_type = fields.Selection(
        CONTRACTOR_TYPES,
        string='Loại nhà thầu',
        default='subcontractor', required=True, tracking=True,
    )

    # ===== Group 3: Project relationship & lifecycle =====

    project_ids = fields.Many2many(
        're.project',
        'rp_contractor_project_rel',
        'contractor_id', 'project_id',
        string='Dự án tham gia',
        help='Projects this contractor has worked on or is currently '
             'engaged with. Auto-populated when a tender package or '
             'contract references this contractor.',
    )
    project_count = fields.Integer(
        compute='_compute_project_count', store=False,
    )

    primary_contact_name = fields.Char(string='Người liên hệ')
    primary_contact_phone = fields.Char(string='SĐT liên hệ')
    primary_contact_email = fields.Char(string='Email liên hệ')

    state = fields.Selection(
        STATES, string='State',
        default='prospect', required=True,
        tracking=True, readonly=True, copy=False,
    )

    notes = fields.Text(string='Ghi chú')
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', string='Company',
        default=lambda self: self.env.company,
    )

    # ===== Computeds =====

    @api.depends('construction_license_expiry')
    def _compute_license_expired(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.construction_license_expiry:
                rec.construction_license_expired = (
                    rec.construction_license_expiry < today
                )
            else:
                rec.construction_license_expired = False

    @api.depends('project_ids')
    def _compute_project_count(self):
        for rec in self:
            rec.project_count = len(rec.project_ids)

    # ===== Constraints =====

    @api.constrains('tax_code')
    def _check_tax_code_format(self):
        for rec in self:
            if not rec.tax_code:
                continue
            # Strip whitespace and hyphens for validation
            digits = rec.tax_code.replace('-', '').replace(' ', '')
            if not digits.isdigit():
                raise ValidationError(
                    f'Mã số thuế "{rec.tax_code}" chỉ được chứa chữ số '
                    f'(có thể kèm dấu - hoặc khoảng trắng).'
                )
            if len(digits) not in (10, 13):
                raise ValidationError(
                    f'Mã số thuế "{rec.tax_code}" phải có 10 hoặc 13 chữ số. '
                    f'Đang có: {len(digits)} chữ số.'
                )

    def init(self):
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS rp_contractor_unique_code_per_company
            ON rp_contractor (company_id, code)
            WHERE code IS NOT NULL
        """)

    # ===== State transitions =====

    def action_approve(self):
        for rec in self:
            if rec.state not in ('prospect', 'suspended'):
                raise UserError(
                    f'Cannot approve contractor in state "{rec.state}". '
                    'Valid source states: prospect, suspended.'
                )
            rec.state = 'approved'

    def action_suspend(self):
        for rec in self:
            if rec.state != 'approved':
                raise UserError(
                    'Only an approved contractor can be suspended.'
                )
            rec.state = 'suspended'

    def action_blacklist(self):
        if not self.env.user.has_group('re_base.group_re_admin'):
            raise UserError(
                'Only Realty admins can blacklist a contractor. '
                'This action is irreversible from this state.'
            )
        for rec in self:
            rec.state = 'blacklisted'

    def action_reset_to_prospect(self):
        if not self.env.user.has_group('re_base.group_re_admin'):
            raise UserError(
                'Only Realty admins can reset state to prospect.'
            )
        for rec in self:
            rec.state = 'prospect'

    # ===== Display =====

    @api.depends('name', 'code')
    def _compute_display_name(self):
        for rec in self:
            if rec.code:
                rec.display_name = f'[{rec.code}] {rec.name or ""}'.strip()
            else:
                rec.display_name = rec.name or ''
