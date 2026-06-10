# -*- coding: utf-8 -*-
"""
Chứng thư bảo lãnh ngân hàng (Letter of Guarantee — LG / BG).

NH phát hành chứng thư cam kết trả tiền cho bên thụ hưởng nếu khách
hàng vi phạm nghĩa vụ. Loại phổ biến VN: dự thầu, thực hiện HĐ, tạm
ứng, bảo hành, thanh toán.

Lifecycle chuẩn (workflow mới):
  draft → issued → (extended) → SETTLED (auto khi đủ phí+ký quỹ+phạt)
  Side branches: released (legacy giải tỏa) / expired / forfeited

Chứng thư thường được auto-created từ re.guarantee.request khi user
bấm "Phát hành" trên đề nghị BL. Theo dõi thanh toán + trả nợ trực
tiếp trên chứng thư (phí BL, ký quỹ, phạt trả chậm). Khi đủ thanh
toán cả 3 nhóm → auto chuyển 'settled' → khôi phục hạn mức facility.
"""
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


GUARANTEE_TYPES = [
    ('bid',         'Bảo lãnh dự thầu (Bid Bond)'),
    ('performance', 'Bảo lãnh thực hiện HĐ (Performance Bond)'),
    ('advance',     'Bảo lãnh tạm ứng (Advance Payment)'),
    ('warranty',    'Bảo lãnh bảo hành (Warranty)'),
    ('payment',     'Bảo lãnh thanh toán (Payment Guarantee)'),
    ('other',       'Khác'),
]


class ReBankGuarantee(models.Model):
    _name = 're.bank.guarantee'
    _description = 'Chứng thư Bảo lãnh ngân hàng'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_issue desc, id desc'

    name = fields.Char(
        string='Số chứng thư', required=True, copy=False, tracking=True,
        default=lambda self: _('/'),
        help='Số chứng thư NH cấp. Auto sequence nếu để trống.')
    guarantee_type = fields.Selection(
        GUARANTEE_TYPES, string='Loại BL', required=True, tracking=True,
        default='performance')

    # --- Các bên ---
    issuing_bank_partner_id = fields.Many2one(
        'res.partner', string='NH phát hành', required=True, tracking=True,
        domain="[('is_bank', '=', True)]")
    issuing_bank_id = fields.Many2one(
        'res.bank', string='Chi nhánh NH',
        domain="[('partner_id', '=', issuing_bank_partner_id)]",
        help='Chi nhánh NH phát hành. Lọc theo NH ở trên.')
    applicant_partner_id = fields.Many2one(
        'res.partner', string='Bên xin BL (Applicant)', required=True,
        tracking=True,
        help='Người mua bảo lãnh — thường là CC1 hoặc nhà thầu phụ.')
    beneficiary_partner_id = fields.Many2one(
        'res.partner', string='Bên thụ hưởng (Beneficiary)', required=True,
        tracking=True,
        help='Bên nhận BL — vd CĐT (khi CC1 mua) hoặc CC1 (khi nhà thầu '
             'phụ mua đưa cho CC1).')

    # --- Thời gian ---
    date_issue = fields.Date(
        string='Ngày phát hành', required=True, tracking=True,
        default=fields.Date.context_today)
    date_expiry = fields.Date(
        string='Ngày hết hạn', required=True, tracking=True)
    days_remaining = fields.Integer(
        string='Số ngày còn lại', compute='_compute_days_remaining')
    is_expiring_soon = fields.Boolean(
        compute='_compute_days_remaining',
        help='True nếu còn ≤ 30 ngày tới hết hạn.')
    is_expired = fields.Boolean(
        compute='_compute_days_remaining',
        help='True nếu đã quá ngày hết hạn.')

    # --- Giá trị + Phí + Ký quỹ ---
    currency_id = fields.Many2one(
        'res.currency', string='Loại tiền', required=True,
        default=lambda self: self.env.company.currency_id)
    amount = fields.Monetary(
        string='Giá trị BL', required=True, tracking=True,
        help='Giá trị NH cam kết trả nếu vi phạm.')
    guarantee_fee_rate = fields.Float(
        string='Phí BL (%/năm)', digits=(5, 2),
        help='Tỷ lệ phí NH thu trên giá trị BL theo năm.')
    guarantee_fee_amount = fields.Monetary(
        string='Phí BL (số tiền)',
        compute='_compute_fee_amount', store=True, readonly=False,
        help='Auto = giá trị × tỷ lệ × số ngày / 365. User có thể '
             'sửa tay nếu NH tính khác.')
    guarantee_fee_paid = fields.Boolean(
        string='Đã trả phí BL (legacy)', tracking=True,
        help='Flag legacy. Workflow mới: theo dõi qua payment_ids '
             '+ guarantee_fee_paid_amount.')
    deposit_rate = fields.Float(
        string='Ký quỹ (%)', digits=(5, 2),
        help='Tỷ lệ ký quỹ trên giá trị BL.')
    deposit_amount = fields.Monetary(
        string='Số tiền ký quỹ',
        compute='_compute_deposit_amount', store=True, readonly=False)

    # --- Phạt trả chậm — tự compute từ overdue days ---
    penalty_rate = fields.Float(
        string='Tỷ lệ phạt trả chậm (%/năm)', digits=(5, 2), default=10.0,
        help='Phạt trả chậm áp lên số phí + ký quỹ chưa trả khi quá '
             'date_expiry. Mặc định 10%/năm.')
    penalty_days = fields.Integer(
        string='Số ngày quá hạn',
        compute='_compute_penalty', store=True)
    penalty_amount = fields.Monetary(
        string='Tiền phạt phải trả',
        compute='_compute_penalty', store=True, readonly=False,
        tracking=True)

    # --- Tracking thanh toán (workflow mới) ---
    guarantee_fee_paid_amount = fields.Monetary(
        string='Phí BL đã trả',
        compute='_compute_paid_totals', store=True, readonly=True,
        tracking=True)
    guarantee_fee_remaining = fields.Monetary(
        string='Phí BL còn phải trả',
        compute='_compute_paid_totals', store=True)
    deposit_paid_amount = fields.Monetary(
        string='Ký quỹ đã nộp',
        compute='_compute_paid_totals', store=True, readonly=True,
        tracking=True)
    deposit_remaining = fields.Monetary(
        string='Ký quỹ còn phải nộp',
        compute='_compute_paid_totals', store=True)
    penalty_paid_amount = fields.Monetary(
        string='Phạt đã trả',
        compute='_compute_paid_totals', store=True, readonly=True,
        tracking=True)
    penalty_remaining = fields.Monetary(
        string='Phạt còn phải trả',
        compute='_compute_paid_totals', store=True)
    principal_paid_amount = fields.Monetary(
        string='Tiền gốc đã trả',
        compute='_compute_paid_totals', store=True, readonly=True,
        tracking=True)
    principal_remaining = fields.Monetary(
        string='Tiền gốc còn phải trả',
        compute='_compute_paid_totals', store=True,
        help='= Giá trị BL − Tổng các đợt thanh toán loại "Tiền gốc". '
             'Auto-settle yêu cầu mục này = 0.')
    total_due = fields.Monetary(
        string='Tổng phải thanh toán',
        compute='_compute_total_due', store=True,
        help='= Phí BL + Ký quỹ + Phạt.')
    total_paid = fields.Monetary(
        string='Tổng đã thanh toán',
        compute='_compute_paid_totals', store=True)
    is_fully_paid = fields.Boolean(
        string='Đã thanh toán đủ',
        compute='_compute_paid_totals', store=True,
        help='True khi cả 3 nhóm (phí + ký quỹ + phạt) đều paid >= '
             'amount. Auto chuyển settled khi True + state ∈ (issued, '
             'extended).')

    # Payment lines
    payment_ids = fields.One2many(
        're.bank.guarantee.payment', 'guarantee_id',
        string='Các đợt thanh toán')
    payment_count = fields.Integer(compute='_compute_payment_count')

    # --- Back-link tới đề nghị BL ---
    guarantee_request_id = fields.Many2one(
        're.guarantee.request', string='Đề nghị BL',
        copy=False, readonly=True,
        help='Đề nghị phát hành BL đã tạo ra chứng thư này. Link 2 chiều.')

    # --- Link với facility (chiếm hạn mức) ---
    facility_id = fields.Many2one(
        're.loan.facility', string='Hạn mức BL',
        domain="[('purpose', '=', 'bank_guarantee')]",
        help='Facility có Mục đích = "Bảo lãnh" mà BL này dùng. '
             'Khi state=issued, BL chiếm hạn mức = giá trị BL.')
    credit_contract_id = fields.Many2one(
        're.loan.credit.contract', string='HĐTD',
        related='facility_id.credit_contract_id', store=True, readonly=True)

    # --- State machine ---
    state = fields.Selection(
        [('draft',     'Nháp'),
         ('issued',    'Đã phát hành'),
         ('extended',  'Đã gia hạn'),
         ('settled',   'Đã tất toán'),
         ('released',  'Đã giải tỏa (legacy)'),
         ('expired',   'Hết hạn'),
         ('forfeited', 'Bị thu (NH trả thay)')],
        string='Trạng thái', default='draft', required=True, tracking=True)

    date_settled = fields.Date(string='Ngày tất toán', readonly=True)
    date_released = fields.Date(string='Ngày giải tỏa', readonly=True)
    release_reason = fields.Char(string='Lý do giải tỏa')
    date_forfeited = fields.Date(string='Ngày bị thu', readonly=True)
    forfeit_reason = fields.Text(string='Lý do bị thu')
    forfeit_amount = fields.Monetary(
        string='Số tiền NH đã trả thay',
        help='Số tiền NH thực tế trả cho beneficiary khi BL bị thu.')

    # --- Phụ lục + Audit ---
    amendment_ids = fields.One2many(
        're.bank.guarantee.amendment', 'guarantee_id',
        string='Phụ lục chứng thư')
    amendment_count = fields.Integer(compute='_compute_amendment_count')

    description = fields.Text(string='Mô tả / Điều khoản')
    legal_text = fields.Html(
        string='Nội dung chứng thư',
        help='Nội dung văn bản chứng thư (copy từ PDF nếu cần).')

    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company)
    active = fields.Boolean(default=True)

    # ==================================================================
    # Computes
    # ==================================================================
    @api.depends('date_expiry')
    def _compute_days_remaining(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.date_expiry:
                delta = (rec.date_expiry - today).days
                rec.days_remaining = delta
                rec.is_expiring_soon = 0 <= delta <= 30
                rec.is_expired = delta < 0
            else:
                rec.days_remaining = 0
                rec.is_expiring_soon = False
                rec.is_expired = False

    @api.depends('amount', 'guarantee_fee_rate',
                 'date_issue', 'date_expiry')
    def _compute_fee_amount(self):
        """Phí BL = giá trị × tỷ lệ × số ngày hiệu lực / 365.
        Robust: nếu date_issue > date_expiry, fee = 0 (data invalid).
        """
        for rec in self:
            if (rec.amount and rec.guarantee_fee_rate
                    and rec.date_issue and rec.date_expiry
                    and rec.date_expiry > rec.date_issue):
                days = (rec.date_expiry - rec.date_issue).days
                rec.guarantee_fee_amount = (
                    rec.amount * rec.guarantee_fee_rate / 100.0
                    * days / 365.0)
            elif not rec.guarantee_fee_amount:
                rec.guarantee_fee_amount = 0.0

    @api.depends('amount', 'deposit_rate')
    def _compute_deposit_amount(self):
        for rec in self:
            if rec.amount and rec.deposit_rate:
                rec.deposit_amount = (
                    rec.amount * rec.deposit_rate / 100.0)
            elif not rec.deposit_amount:
                rec.deposit_amount = 0.0

    @api.depends('amendment_ids')
    def _compute_amendment_count(self):
        for rec in self:
            rec.amendment_count = len(rec.amendment_ids)

    @api.depends('date_expiry', 'amount', 'penalty_rate', 'state')
    def _compute_penalty(self):
        """Công thức chuẩn NH:
            penalty = giá trị BL × tỷ lệ phạt × số ngày quá hạn / 365
        Áp lên TOÀN BỘ giá trị BL (không chỉ phần phí/ký quỹ chưa trả).
        """
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.state not in ('issued', 'extended') or not rec.date_expiry:
                rec.penalty_days = 0
                rec.penalty_amount = 0.0
                continue
            overdue = (today - rec.date_expiry).days
            if overdue <= 0:
                rec.penalty_days = 0
                rec.penalty_amount = 0.0
                continue
            rec.penalty_days = overdue
            rec.penalty_amount = (
                rec.amount * (rec.penalty_rate or 0) / 100.0
                * overdue / 365.0)

    @api.depends('guarantee_fee_amount', 'deposit_amount', 'penalty_amount')
    def _compute_total_due(self):
        """Tổng phải thanh toán =
            Số tiền ký quỹ phải nộp + Tiền phạt phải trả + Phí BL phải trả.
        """
        for rec in self:
            rec.total_due = (
                rec.deposit_amount
                + rec.penalty_amount
                + rec.guarantee_fee_amount)

    @api.depends('payment_ids.amount', 'payment_ids.payment_kind',
                 'payment_ids.state',
                 'guarantee_fee_amount', 'deposit_amount',
                 'penalty_amount', 'amount')
    def _compute_paid_totals(self):
        """Auto-settle yêu cầu đủ 4 loại đã trả:
            Phí BL + Ký quỹ + Phạt + Tiền gốc (= giá trị BL).
        """
        for rec in self:
            posted = rec.payment_ids.filtered(lambda p: p.state == 'posted')
            fee_paid = sum(
                posted.filtered(lambda p: p.payment_kind == 'fee')
                .mapped('amount'))
            dep_paid = sum(
                posted.filtered(lambda p: p.payment_kind == 'deposit')
                .mapped('amount'))
            pen_paid = sum(
                posted.filtered(lambda p: p.payment_kind == 'penalty')
                .mapped('amount'))
            prin_paid = sum(
                posted.filtered(lambda p: p.payment_kind == 'principal')
                .mapped('amount'))
            rec.guarantee_fee_paid_amount = fee_paid
            rec.deposit_paid_amount = dep_paid
            rec.penalty_paid_amount = pen_paid
            rec.principal_paid_amount = prin_paid
            rec.guarantee_fee_remaining = max(
                0, rec.guarantee_fee_amount - fee_paid)
            rec.deposit_remaining = max(0, rec.deposit_amount - dep_paid)
            rec.penalty_remaining = max(0, rec.penalty_amount - pen_paid)
            rec.principal_remaining = max(0, rec.amount - prin_paid)
            rec.total_paid = fee_paid + dep_paid + pen_paid + prin_paid
            rec.is_fully_paid = (
                rec.guarantee_fee_remaining <= 0.01
                and rec.deposit_remaining <= 0.01
                and rec.penalty_remaining <= 0.01
                and rec.principal_remaining <= 0.01)

    @api.depends('payment_ids')
    def _compute_payment_count(self):
        for rec in self:
            rec.payment_count = len(rec.payment_ids)

    # ==================================================================
    # Onchange — clear chi nhánh khi đổi NH
    # ==================================================================
    @api.onchange('issuing_bank_partner_id')
    def _onchange_issuing_bank_partner(self):
        if (self.issuing_bank_id and self.issuing_bank_id.partner_id
                and self.issuing_bank_id.partner_id
                != self.issuing_bank_partner_id):
            self.issuing_bank_id = False

    # ==================================================================
    # Create — auto sequence
    # ==================================================================
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('/')) == _('/'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    're.bank.guarantee') or _('/')
        return super().create(vals_list)

    # ==================================================================
    # Validation
    # ==================================================================
    @api.constrains('date_issue', 'date_expiry')
    def _check_dates(self):
        for rec in self:
            if (rec.date_issue and rec.date_expiry
                    and rec.date_expiry < rec.date_issue):
                raise ValidationError(_(
                    "Ngày hết hạn không được trước ngày phát hành."))

    @api.constrains('amount')
    def _check_amount(self):
        for rec in self:
            if rec.amount <= 0:
                raise ValidationError(_("Giá trị BL phải > 0."))

    # ==================================================================
    # State machine
    # ==================================================================
    def action_issue(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_(
                    "Chỉ BL ở trạng thái Nháp mới phát hành được."))
            rec.state = 'issued'
            rec.message_post(body=_(
                "Phát hành BL — giá trị %(a)s, hết hạn %(d)s.",
                a=rec.amount, d=rec.date_expiry))

    def action_release(self):
        for rec in self:
            if rec.state not in ('issued', 'extended'):
                raise UserError(_(
                    "Chỉ BL Đã phát hành / Đã gia hạn mới giải tỏa được."))
            rec.state = 'released'
            rec.date_released = fields.Date.context_today(rec)
            rec.message_post(body=_(
                "Giải tỏa BL — beneficiary trả lại chứng thư cho NH."))

    def action_forfeit(self):
        for rec in self:
            if rec.state not in ('issued', 'extended'):
                raise UserError(_(
                    "Chỉ BL đang hiệu lực mới có thể bị thu."))
            rec.state = 'forfeited'
            rec.date_forfeited = fields.Date.context_today(rec)
            rec.message_post(body=_(
                "BL bị thu — NH trả thay %(a)s cho beneficiary '%(b)s'.",
                a=rec.forfeit_amount or rec.amount,
                b=rec.beneficiary_partner_id.name or ''))

    def action_settle(self):
        """Tất toán BL — khôi phục hạn mức facility.

        Workflow mới: state issued/extended/forfeited → settled khi
        đã thanh toán đủ (auto qua _check_auto_settle, hoặc manual
        qua nút).

        Case 'forfeited': NH đã trả tiền thay beneficiary; applicant
        hoàn trả NH (principal + phí + ký quỹ + phạt) → settled →
        khôi phục hạn mức (vì BL không còn outstanding obligation).
        """
        for rec in self:
            if rec.state not in ('issued', 'extended', 'forfeited'):
                raise UserError(_(
                    "Chỉ BL Đã phát hành / Gia hạn / Bị thu mới tất "
                    "toán được."))
            rec.state = 'settled'
            rec.date_settled = fields.Date.context_today(rec)
            # Recompute facility — settled cert không còn trong
            # guarantee_total_outstanding → hạn mức khôi phục.
            if rec.facility_id:
                rec.facility_id._compute_guarantee_stats()
                rec.facility_id._compute_amount_used()
                rec.facility_id._compute_amount_available()
            rec.message_post(body=_(
                "Tất toán BL — khôi phục hạn mức %(f)s.",
                f=rec.facility_id.name or ''))

    def _check_auto_settle(self):
        """Nếu fully paid + state in (issued, extended, forfeited)
        → auto settle."""
        for rec in self.filtered(
                lambda r: r.state in ('issued', 'extended', 'forfeited')
                and r.is_fully_paid):
            rec.action_settle()

    def action_view_payments(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Thanh toán — %s") % self.name,
            'res_model': 're.bank.guarantee.payment',
            'view_mode': 'list,form',
            'domain': [('guarantee_id', '=', self.id)],
            'context': {
                'default_guarantee_id': self.id,
                'default_currency_id': self.currency_id.id,
            },
        }

    def action_reset_draft(self):
        for rec in self:
            if rec.state in ('released', 'forfeited', 'settled'):
                raise UserError(_(
                    "Không thể đưa BL %s về Nháp.", rec.state))
            rec.state = 'draft'
            rec.date_released = False
            rec.date_forfeited = False
            rec.date_settled = False

    # ==================================================================
    # Cron — auto đặt expired + nhắc sắp hết hạn
    # ==================================================================
    @api.model
    def _cron_check_expiry(self):
        """Cron daily:
          - BL state='issued'/'extended' đã quá hạn 7+ ngày mà chưa giải
            tỏa → tự đặt state='expired'
          - BL sắp hết hạn 30 ngày → tạo activity nhắc người phụ trách
        """
        today = fields.Date.context_today(self)
        # 1. Auto expire
        expired = self.search([
            ('state', 'in', ('issued', 'extended')),
            ('date_expiry', '<', today - timedelta(days=7)),
        ])
        for rec in expired:
            rec.state = 'expired'
            rec.message_post(body=_(
                "BL tự động chuyển trạng thái Hết hạn (quá 7 ngày kể "
                "từ ngày hết hạn mà chưa giải tỏa)."))
        # 2. Notify expiring soon
        expiring = self.search([
            ('state', 'in', ('issued', 'extended')),
            ('date_expiry', '<=', today + timedelta(days=30)),
            ('date_expiry', '>=', today),
        ])
        for rec in expiring:
            existing = rec.activity_ids.filtered(
                lambda a: a.summary == 'BL sắp hết hạn')
            if existing:
                continue
            rec.activity_schedule(
                'mail.mail_activity_data_todo',
                summary='BL sắp hết hạn',
                note=_(
                    'BL %(name)s hết hạn ngày %(d)s (còn %(n)s ngày). '
                    'Cân nhắc gia hạn hoặc giải tỏa.',
                    name=rec.name, d=rec.date_expiry,
                    n=rec.days_remaining))


class ReBankGuaranteePayment(models.Model):
    _name = 're.bank.guarantee.payment'
    _description = 'Đợt thanh toán Chứng thư BL'
    _order = 'date desc, id desc'

    guarantee_id = fields.Many2one(
        're.bank.guarantee', string='Chứng thư BL',
        required=True, ondelete='cascade')
    name = fields.Char(string='Diễn giải')
    date = fields.Date(
        string='Ngày thanh toán', required=True,
        default=fields.Date.context_today)
    payment_kind = fields.Selection(
        [('fee',       'Phí BL'),
         ('deposit',   'Ký quỹ'),
         ('penalty',   'Phạt quá hạn'),
         ('principal', 'Tiền gốc')],
        string='Loại thanh toán', required=True, default='fee',
        help='Tiền gốc: hoàn trả NH số tiền NH đã trả thay cho '
             'beneficiary (khi BL bị thu / forfeited).')
    amount = fields.Monetary(string='Số tiền', required=True)
    reference = fields.Char(string='Số chứng từ NH')
    state = fields.Selection(
        [('draft',  'Nháp'),
         ('posted', 'Đã xác nhận')],
        string='Trạng thái', default='posted', required=True)

    currency_id = fields.Many2one(
        related='guarantee_id.currency_id', store=True, readonly=True)
    company_id = fields.Many2one(
        related='guarantee_id.company_id', store=True, readonly=True)

    @api.constrains('amount')
    def _check_amount(self):
        for rec in self:
            if rec.amount <= 0:
                raise ValidationError(_(
                    "Số tiền thanh toán phải > 0."))

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        recs.guarantee_id._check_auto_settle()
        return recs

    def write(self, vals):
        res = super().write(vals)
        self.guarantee_id._check_auto_settle()
        return res
