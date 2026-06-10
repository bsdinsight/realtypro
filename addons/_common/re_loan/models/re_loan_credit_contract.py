# -*- coding: utf-8 -*-
"""
Hợp đồng tín dụng (HĐTD) — Master Credit Agreement.

Hợp đồng khung ký với ngân hàng. Dưới mỗi HĐTD có 1..n hạn mức (facility);
mỗi lần rút vốn trong hạn mức tạo 1 khế ước nhận nợ (re.loan.note, phase L1b).
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class ReLoanCreditContract(models.Model):
    _name = 're.loan.credit.contract'
    _description = 'Hợp đồng tín dụng (HĐTD)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sign_date desc, id desc'

    name = fields.Char(
        string='Số HĐTD', required=True, copy=False, tracking=True,
        help='Số hợp đồng tín dụng do ngân hàng cấp (nhập tay).')
    partner_id = fields.Many2one(
        'res.partner', string='Ngân hàng / Bên cho vay', required=True,
        tracking=True, domain="[('is_bank', '=', True)]",
        help='Đánh dấu đối tác là Bank/Lender trên Contact để hiện ở đây.')
    bank_id = fields.Many2one(
        'res.bank', string='Chi nhánh / Mã NH',
        domain="[('partner_id', '=', partner_id)]",
        help='Tham chiếu res.bank (chi nhánh, mã NH). CHỈ hiện các res.bank '
             'thuộc Ngân hàng đã chọn — nếu trống thì cần chọn NH trước.')

    @api.onchange('partner_id')
    def _onchange_partner_clear_bank(self):
        # Khi đổi NH, xoá chi nhánh nếu không khớp partner mới.
        if self.bank_id and self.bank_id.partner_id \
                and self.bank_id.partner_id != self.partner_id:
            self.bank_id = False
    company_id = fields.Many2one(
        'res.company', string='Công ty (bên vay)', required=True,
        default=lambda self: self.env.company, tracking=True)
    currency_id = fields.Many2one(
        'res.currency', string='Loại tiền', required=True,
        default=lambda self: self.env.company.currency_id)

    sign_date = fields.Date(string='Ngày ký', tracking=True)
    date_start = fields.Date(string='Ngày hiệu lực')
    date_end = fields.Date(string='Ngày hết hạn', tracking=True)
    amount_total = fields.Monetary(
        string='Tổng hạn mức HĐTD', required=True, tracking=True)
    representative = fields.Char(string='Người đại diện ký')

    state = fields.Selection(
        [('draft', 'Nháp'),
         ('active', 'Hiệu lực'),
         ('expired', 'Hết hạn'),
         ('closed', 'Đã tất toán'),
         ('cancelled', 'Đã huỷ')],
        string='Trạng thái', default='draft', required=True, tracking=True)

    facility_ids = fields.One2many(
        're.loan.facility', 'credit_contract_id', string='Hạn mức')
    pledge_ids = fields.One2many(
        're.loan.collateral.pledge', 'credit_contract_id',
        string='Tài sản thế chấp',
        domain="[('pledge_target', '=', 'contract')]")
    pledge_count = fields.Integer(
        compute='_compute_pledge_count')

    def _compute_pledge_count(self):
        for rec in self:
            rec.pledge_count = len(rec.pledge_ids.filtered(
                lambda p: p.pledge_target == 'contract'))
    facility_count = fields.Integer(
        string='Số hạn mức', compute='_compute_facility_stats')
    amount_facility_total = fields.Monetary(
        string='Tổng hạn mức đã cấp', compute='_compute_facility_stats',
        store=True,
        help='Tổng hạn mức của các facility dưới HĐTD này.')
    amount_facility_available = fields.Monetary(
        string='Hạn mức HĐTD còn lại', compute='_compute_facility_stats',
        help='Tổng hạn mức HĐTD trừ đi tổng hạn mức đã cấp cho các facility.')
    amount_pool_used = fields.Monetary(
        string='Tổng đã dùng (Σ facility)', compute='_compute_pool_stats',
        store=True,
        help='Tổng "đã dùng" của tất cả facility (mọi mục đích).')
    amount_pool_available = fields.Monetary(
        string='HĐTD còn lại (Σ)', compute='_compute_pool_stats', store=True,
        help='= Tổng HĐTD − Tổng đã dùng. Là số tiền tối đa toàn HĐTD '
             'còn có thể rút thêm (gộp mọi mục đích).')

    has_flexible_facility = fields.Boolean(
        string='Có facility liên thông',
        compute='_compute_has_flexible_facility',
        help='HĐTD có ít nhất 1 facility tick liên thông — các facility '
             'liên thông chia sẻ phần thừa hạn mức với nhau.')

    note = fields.Text(string='Ghi chú')
    active = fields.Boolean(default=True)

    # ------------------------------------------------------------------
    # Compute
    # ------------------------------------------------------------------
    @api.depends('facility_ids.amount_limit', 'amount_total')
    def _compute_facility_stats(self):
        for rec in self:
            rec.facility_count = len(rec.facility_ids)
            rec.amount_facility_total = sum(
                rec.facility_ids.mapped('amount_limit'))
            rec.amount_facility_available = (
                rec.amount_total - rec.amount_facility_total)

    @api.depends('facility_ids.amount_used', 'amount_total')
    def _compute_pool_stats(self):
        for rec in self:
            rec.amount_pool_used = sum(
                rec.facility_ids.mapped('amount_used'))
            rec.amount_pool_available = (
                rec.amount_total - rec.amount_pool_used)

    @api.depends('facility_ids.flexible_limits')
    def _compute_has_flexible_facility(self):
        for rec in self:
            rec.has_flexible_facility = any(
                rec.facility_ids.mapped('flexible_limits'))

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------
    @api.constrains('amount_total', 'facility_ids')
    def _check_facility_total(self):
        # HARD RULE: Σ limit của tất cả facility ≤ tổng HĐTD. Luôn áp
        # dụng — tick liên thông trên facility chỉ chia sẻ pool phần
        # thừa, KHÔNG bypass total HĐTD.
        for rec in self:
            if rec.amount_facility_total > rec.amount_total:
                raise ValidationError(_(
                    "Tổng hạn mức các facility (%(fac)s) vượt quá tổng "
                    "hạn mức HĐTD (%(total)s). Σ limit luôn phải ≤ HĐTD "
                    "— 'Hạn mức liên thông' trên facility chỉ chia sẻ "
                    "phần thừa trong pool, không cho phép vượt total.",
                    fac=rec.amount_facility_total, total=rec.amount_total))

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for rec in self:
            if rec.date_start and rec.date_end \
                    and rec.date_end < rec.date_start:
                raise ValidationError(_(
                    "Ngày hết hạn không được trước ngày hiệu lực."))

    # ------------------------------------------------------------------
    # State machine
    # ------------------------------------------------------------------
    def action_activate(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_(
                    "Chỉ có thể kích hoạt HĐTD đang ở trạng thái Nháp."))
            rec.state = 'active'

    def action_set_expired(self):
        for rec in self:
            if rec.state != 'active':
                raise UserError(_("Chỉ HĐTD đang Hiệu lực mới hết hạn được."))
            rec.state = 'expired'

    def action_close(self):
        for rec in self:
            if rec.state not in ('active', 'expired'):
                raise UserError(_(
                    "Chỉ HĐTD Hiệu lực/Hết hạn mới tất toán được."))
            rec.state = 'closed'

    def action_cancel(self):
        for rec in self:
            if rec.state == 'closed':
                raise UserError(_("Không thể huỷ HĐTD đã tất toán."))
            rec.state = 'cancelled'

    def action_reset_draft(self):
        for rec in self:
            if rec.state not in ('cancelled',):
                raise UserError(_(
                    "Chỉ HĐTD đã huỷ mới đưa về Nháp được."))
            rec.state = 'draft'

    # ------------------------------------------------------------------
    # Guards
    # ------------------------------------------------------------------
    def unlink(self):
        for rec in self:
            if rec.facility_ids:
                raise UserError(_(
                    "Không thể xoá HĐTD '%s' khi còn hạn mức. Huỷ thay vì "
                    "xoá để giữ vết.", rec.name))
        return super().unlink()
