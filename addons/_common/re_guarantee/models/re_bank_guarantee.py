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
from odoo.tools import clean_context


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
        help='Người mua bảo lãnh — thường là tổng thầu hoặc nhà thầu phụ.')
    beneficiary_partner_id = fields.Many2one(
        'res.partner', string='Bên thụ hưởng (Beneficiary)', required=True,
        tracking=True,
        help='Bên nhận BL — vd CĐT (khi tổng thầu mua) hoặc tổng thầu (khi nhà thầu '
             'phụ mua đưa cho tổng thầu).')

    # --- Thời gian ---
    date_issue = fields.Date(
        string='Ngày phát hành', required=True, tracking=True,
        default=fields.Date.context_today)
    date_activation = fields.Date(
        string='Ngày kích hoạt', tracking=True, copy=False,
        help='Ngày BL chính thức bắt đầu có hiệu lực (NH ký + người '
             'thụ hưởng nhận). Nếu trống → fallback date_issue. Phí '
             'BL tính từ ngày này đến date_expiry.')
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
    fee_schedule_freq = fields.Selection(
        [('monthly',    'Hàng tháng'),
         ('quarterly',  'Hàng quý'),
         ('semiannual', '6 tháng'),
         ('annual',     'Hàng năm')],
        string='Tần suất trả phí BL', default='quarterly',
        help='Chu kỳ thanh toán Phí BL — dùng cho nút "Tạo lịch phí '
             'BL" (khách hàng #11): chia phí theo đợt, số tiền mỗi đợt '
             'pro-rata theo SỐ NGÀY của đợt.')
    fee_first_payment = fields.Monetary(
        string='Phí BL trả lần đầu',
        help='khách hàng #12: khoản phí NH thu NGAY khi phát hành (như ký '
             'quỹ) — thành Đợt 1 riêng, hạn = ngày kích hoạt/phát '
             'hành. Phần còn lại (tổng phí − lần đầu) chia vào các '
             'kỳ theo tần suất. Để 0 nếu NH không thu trước.')
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
    account_payment_count = fields.Integer(
        string='Số phiếu chi', compute='_compute_payment_missing',
        help='Số phiếu chi / phiếu thu thật trong sổ kế toán sinh từ '
             'chứng thư này. Khác với "Đợt thanh toán" — đó là bảng '
             'theo dõi nghĩa vụ của chứng thư.')
    payment_missing_count = fields.Integer(
        string='Đợt chưa có phiếu chi',
        compute='_compute_payment_missing',
        help='Số đợt thanh toán ĐÃ xác nhận nhưng chưa sinh phiếu chi. '
             'Thường là đợt ghi nhận trước khi có tính năng này, hoặc '
             'ghi lúc chưa khai tài khoản kế toán.')
    deposit_refund_payment_id = fields.Many2one(
        'account.payment', string='Phiếu thu hoàn ký quỹ',
        readonly=True, copy=False, ondelete='set null',
        help='Phiếu thu ghi nhận ngân hàng trả lại tiền ký quỹ khi '
             'chứng thư kết thúc. Chưa có phiếu này thì số dư ký quỹ '
             '(TK 244) còn treo dù chứng thư đã đóng.')
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

    # Đợt thanh toán (kế hoạch) — header
    schedule_ids = fields.One2many(
        're.bank.guarantee.payment.schedule', 'guarantee_id',
        string='Các đợt thanh toán')
    schedule_count = fields.Integer(compute='_compute_schedule_count')

    # Payment transactions (lần thanh toán thực tế) — ledger
    payment_ids = fields.One2many(
        're.bank.guarantee.payment', 'guarantee_id',
        string='Lịch sử thanh toán')
    payment_count = fields.Integer(compute='_compute_payment_count')

    # --- Back-link tới đề nghị BL ---
    guarantee_request_id = fields.Many2one(
        're.guarantee.request', string='Đề nghị BL',
        copy=False, readonly=True,
        help='Đề nghị phát hành BL đã tạo ra chứng thư này. Link 2 chiều.')

    # --- Link với facility (chiếm hạn mức) ---
    facility_id = fields.Many2one(
        're.loan.facility', string='Hạn mức BL',
        domain="[('purpose_kind', '=', 'guarantee')]",
        help='Hạn mức có Mục đích thuộc nhóm "Bảo lãnh" mà BL này '
             'dùng. Khi state=issued, BL chiếm hạn mức = giá trị BL.')
    credit_contract_id = fields.Many2one(
        're.loan.credit.contract', string='HĐTD',
        related='facility_id.credit_contract_id', store=True, readonly=True)

    # --- State machine ---
    state = fields.Selection(
        [('draft',     'Nháp'),
         ('issued',    'Đã phát hành'),
         ('extended',  'Đã gia hạn'),
         ('settled',   'Đã tất toán'),
         ('released',  'Đã huỷ / giải toả'),
         ('expired',   'Hết hạn'),
         ('forfeited', 'Bị thu (NH trả thay)')],
        string='Trạng thái', default='draft', required=True, tracking=True)

    # ── Người phụ trách ───────────────────────────────────────────
    # Không có PIC thì cảnh báo sắp hết hạn không biết gửi cho ai —
    # gửi cả nhóm quản trị thì thành thư rác, ai cũng tưởng người khác
    # lo. Một cái tên trên chứng thư là điều kiện để nhắc có địa chỉ.
    pic_user_id = fields.Many2one(
        'res.users', string='Người phụ trách (PIC)', tracking=True,
        index=True,
        help='Người nhận thư nhắc khi bảo lãnh sắp hết hạn.')
    pic_department_id = fields.Many2one(
        'hr.department', string='Phòng ban', tracking=True)

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
                 'date_issue', 'date_activation', 'date_expiry')
    def _compute_fee_amount(self):
        """Phí BL = giá trị × tỷ lệ × số ngày hiệu lực / 365.

        Ngày bắt đầu hiệu lực: ưu tiên date_activation, fallback
        date_issue. Robust: nếu start > expiry, fee = 0 (data invalid).
        """
        for rec in self:
            start = rec.date_activation or rec.date_issue
            if (rec.amount and rec.guarantee_fee_rate
                    and start and rec.date_expiry
                    and rec.date_expiry > start):
                days = (rec.date_expiry - start).days
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

    @api.depends('schedule_ids')
    def _compute_schedule_count(self):
        for rec in self:
            rec.schedule_count = len(rec.schedule_ids)

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
        """Huỷ / giải toả chứng thư — hạn mức được trả lại ngay.

        Ghi thêm một dòng sang ĐỀ NGHỊ đã sinh ra chứng thư này: huỷ
        chứng thư mà đề nghị vẫn đứng "Đã phát hành" thì hai văn bản
        nói ngược nhau, người mở đề nghị ra không hiểu vì sao hạn mức
        đã được trả lại.
        """
        for rec in self:
            if rec.state not in ('issued', 'extended'):
                raise UserError(_(
                    "Chỉ BL Đã phát hành / Đã gia hạn mới giải tỏa được."))
            rec.state = 'released'
            rec.date_released = fields.Date.context_today(rec)
            request = self.env['re.guarantee.request'].search(
                [('bank_guarantee_id', '=', rec.id)], limit=1)
            if request and request.state not in ('cancelled', 'settled'):
                request.message_post(body=_(
                    "Chứng thư %(c)s đã huỷ/giải toả — hạn mức bảo lãnh "
                    "đã được trả lại. Đề nghị này vẫn đang ở trạng thái "
                    "\"%(s)s\"; huỷ nốt đề nghị nếu không phát hành lại.",
                    c=rec.name,
                    s=dict(request._fields['state'].selection).get(
                        request.state)))
            rec.message_post(body=_(
                "Giải tỏa BL — beneficiary trả lại chứng thư cho NH."))
            if rec.deposit_paid_amount > 0.01:
                rec.message_post(body=_(
                    "Còn %(a)s ₫ ký quỹ tại ngân hàng. Khi NH chuyển "
                    "trả, bấm <b>Ghi nhận thu hoàn ký quỹ</b> để ghi "
                    "phiếu thu và tất toán khoản ký quỹ.",
                    a='{:,.0f}'.format(rec.deposit_paid_amount)))

    @api.depends('payment_ids.state', 'payment_ids.payment_id',
                 'deposit_refund_payment_id')
    def _compute_payment_missing(self):
        for rec in self:
            rec.payment_missing_count = len(rec._pending_payments())
            pays = rec.payment_ids.mapped('payment_id')
            if rec.deposit_refund_payment_id:
                pays |= rec.deposit_refund_payment_id
            rec.account_payment_count = len(pays)

    def _pending_payments(self):
        """Đợt thanh toán đã xác nhận mà chưa có phiếu chi."""
        self.ensure_one()
        return self.payment_ids.filtered(
            lambda p: p.state == 'posted' and not p.payment_id)

    def action_create_missing_payments(self):
        """Sinh bù phiếu chi cho các đợt đã ghi nhận (backlog 969).

        Phiếu chi chỉ sinh Ở LÚC ghi nhận đợt thanh toán, nên mọi đợt
        ghi trước khi có tính năng này không có phiếu nào và không có
        đường nào sinh lại. Nút này là đường đó.
        """
        self.ensure_one()
        pending = self._pending_payments()
        if not pending:
            raise UserError(_(
                "Mọi đợt thanh toán của chứng thư này đã có phiếu chi."))
        Settings = self.env['res.config.settings'].sudo()
        kinds = dict(self.env['re.bank.guarantee.payment']
                     ._fields['payment_kind'].selection)
        # Kiểm ĐỦ tài khoản cho mọi loại đang có trước khi sinh, để
        # không sinh được một nửa rồi dừng giữa chừng.
        for kind in set(pending.mapped('payment_kind')):
            Settings._require_guarantee_account(kind, kinds.get(kind, ''))
        pending._sync_account_payment()
        return True

    def action_view_account_payments(self):
        self.ensure_one()
        payments = self.payment_ids.mapped('payment_id')
        if self.deposit_refund_payment_id:
            payments |= self.deposit_refund_payment_id
        return {
            'type': 'ir.actions.act_window',
            'name': _("Phiếu chi / thu — %s") % (self.name or ''),
            'res_model': 'account.payment',
            'view_mode': 'list,form',
            'domain': [('id', 'in', payments.ids)],
            'context': {'create': False},
        }

    def action_refund_deposit(self):
        """Ghi nhận NH hoàn lại tiền ký quỹ khi BL được giải toả.

        Ký quỹ là TÀI SẢN (TK 244), không phải chi phí — nộp đi thì
        treo ở đó cho tới khi chứng thư kết thúc và ngân hàng trả lại.
        Không có bước này thì số dư 244 nằm lại vĩnh viễn dù chứng thư
        đã đóng (backlog 969).
        """
        self.ensure_one()
        if self.state not in ('released', 'expired', 'settled'):
            raise UserError(_(
                "Chỉ hoàn ký quỹ khi chứng thư đã kết thúc (giải toả / "
                "hết hạn / tất toán)."))
        if self.deposit_refund_payment_id:
            raise UserError(_(
                "Đã ghi nhận hoàn ký quỹ bằng phiếu thu %s.",
                self.deposit_refund_payment_id.name))
        amount = self.deposit_paid_amount
        if amount <= 0.01:
            raise UserError(_(
                "Chứng thư này không có tiền ký quỹ đã nộp."))
        Settings = self.env['res.config.settings'].sudo()
        account = Settings._require_guarantee_account(
            'deposit', _('Ký quỹ'))
        journal = self.env['account.journal'].search([
            ('type', '=', 'bank'), ('company_id', '=', self.company_id.id),
        ], limit=1)
        cfg_journal = Settings._guarantee_payment_journal()
        if cfg_journal and cfg_journal.company_id == self.company_id:
            journal = cfg_journal
        if not journal:
            raise UserError(_(
                "Chưa có sổ nhật ký ngân hàng để ghi phiếu thu."))
        payment = self.env['account.payment'].with_context(
            clean_context(self.env.context)).create({
            'payment_type': 'inbound',
            'partner_type': 'supplier',
            'partner_id': self.issuing_bank_partner_id.id,
            'amount': amount,
            'date': self.date_released or fields.Date.context_today(self),
            'journal_id': journal.id,
            'destination_account_id': account.id,
            'memo': _("Hoàn ký quỹ — BL %s", self.name or ''),
            'guarantee_refund_id': self.id,
        })
        payment.action_post()
        self.deposit_refund_payment_id = payment
        self.message_post(body=_(
            "Đã ghi nhận NH hoàn %(a)s ₫ ký quỹ — phiếu thu %(p)s, "
            "tất toán số dư %(acc)s.",
            a='{:,.0f}'.format(amount), p=payment.name,
            acc=account.display_name))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Phiếu thu hoàn ký quỹ'),
            'res_model': 'account.payment',
            'res_id': payment.id,
            'view_mode': 'form',
        }

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


    # ------------------------------------------------------------------
    # khách hàng #11 — Gen lịch thanh toán Phí BL theo tần suất
    # ------------------------------------------------------------------
    def action_generate_fee_schedule(self):
        """Tự động tạo các đợt thanh toán Phí BL (payment_kind='fee').

        - Chia khoảng [ngày kích hoạt (fallback ngày phát hành) →
          ngày hết hạn] theo tần suất user chọn (tháng/quý/6T/năm)
        - Số tiền mỗi đợt = Tổng phí BL × số ngày của đợt / tổng số
          ngày (đợt cuối nhận phần dư làm tròn)
        - Hạn thanh toán = ngày ĐẦU mỗi đợt (NH thu phí đầu kỳ)
        - Replace các dòng Phí BL CHƯA thanh toán; block nếu có dòng
          phí đã thanh toán (một phần) — tránh phá lịch sử.
        """
        from dateutil.relativedelta import relativedelta
        step_map = {'monthly': 1, 'quarterly': 3, 'semiannual': 6,
                    'annual': 12}
        for rec in self:
            start = rec.date_activation or rec.date_issue
            if not (start and rec.date_expiry
                    and rec.date_expiry > start):
                raise UserError(_(
                    "Cần Ngày kích hoạt/phát hành + Ngày hết hạn hợp "
                    "lệ trước khi tạo lịch phí."))
            if rec.guarantee_fee_amount <= 0:
                raise UserError(_(
                    "Tổng Phí BL = 0 — nhập Tỷ lệ phí hoặc số tiền "
                    "phí trước."))
            fee_lines = rec.schedule_ids.filtered(
                lambda l: l.payment_kind == 'fee')
            if any(l.amount_paid > 0 for l in fee_lines):
                raise UserError(_(
                    "Đã có đợt Phí BL thanh toán (một phần) — không "
                    "regen tự động được. Xoá/điều chỉnh tay các đợt "
                    "chưa trả nếu cần."))
            fee_lines.unlink()

            months = step_map[rec.fee_schedule_freq or 'quarterly']
            total_days = (rec.date_expiry - start).days
            total_fee = rec.guarantee_fee_amount
            # khách hàng #12: phí trả lần đầu tách thành Đợt 1 riêng (thu
            # ngay khi phát hành), phần còn lại chia kỳ pro-rata.
            first_pay = min(rec.fee_first_payment or 0.0, total_fee)
            remain_fee = total_fee - first_pay
            periods = []
            cursor = start
            while cursor < rec.date_expiry:
                period_end = min(
                    cursor + relativedelta(months=months),
                    rec.date_expiry)
                periods.append((cursor, period_end))
                cursor = period_end
            vals_list, allocated = [], 0.0
            seq_offset = 0
            if first_pay > 0:
                seq_offset = 1
                vals_list.append({
                    'guarantee_id': rec.id,
                    'payment_kind': 'fee',
                    'sequence': 10,
                    'due_date': start,
                    'amount_due': first_pay,
                    'name': _("Trả lần đầu - Phí BL (%(d)s)",
                              d=start.strftime('%d/%m/%Y')),
                })
            if remain_fee > 0.01:
                for idx, (p_start, p_end) in enumerate(periods):
                    is_last = idx == len(periods) - 1
                    days = (p_end - p_start).days
                    amt = (remain_fee - allocated if is_last
                           else round(remain_fee * days / total_days))
                    allocated += amt
                    if amt <= 0:
                        continue
                    vals_list.append({
                        'guarantee_id': rec.id,
                        'payment_kind': 'fee',
                        'sequence': (idx + 1 + seq_offset) * 10,
                        'due_date': p_start,
                        'amount_due': amt,
                        'name': _(
                            "Đợt %(n)s - Phí BL (%(f)s → %(t)s, %(d)s ngày)",
                            n=idx + 1 + seq_offset,
                            f=p_start.strftime('%d/%m/%Y'),
                            t=p_end.strftime('%d/%m/%Y'),
                            d=days),
                    })
            self.env['re.bank.guarantee.payment.schedule'].create(
                vals_list)
            rec.message_post(body=_(
                "Đã tạo lịch Phí BL: %(n)s đợt (%(freq)s), tổng "
                "%(amt)s ₫ — trả lần đầu %(first)s ₫, còn lại "
                "pro-rata theo số ngày từng đợt.",
                first='{:,.0f}'.format(first_pay),
                n=len(vals_list),
                freq=dict(rec._fields['fee_schedule_freq'].selection)[
                    rec.fee_schedule_freq or 'quarterly'],
                amt='{:,.0f}'.format(total_fee)))
        return True



class ReBankGuaranteePaymentSchedule(models.Model):
    _name = 're.bank.guarantee.payment.schedule'
    _description = 'Đợt thanh toán Chứng thư BL (kế hoạch)'
    _order = 'guarantee_id, sequence, due_date, id'

    guarantee_id = fields.Many2one(
        're.bank.guarantee', string='Chứng thư BL',
        required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    name = fields.Char(
        string='Diễn giải', compute='_compute_name',
        store=True, readonly=False)
    payment_kind = fields.Selection(
        [('fee',       'Phí BL'),
         ('deposit',   'Ký quỹ'),
         ('penalty',   'Phạt quá hạn'),
         ('principal', 'Tiền gốc')],
        string='Loại thanh toán', required=True, default='fee',
        help='Loại nghĩa vụ phải trả cho NH theo đợt này.')
    due_date = fields.Date(string='Hạn thanh toán', required=True)
    amount_due = fields.Monetary(
        string='Số tiền phải trả', required=True,
        help='Số tiền dự kiến phải trả NH cho đợt này.')

    # Transactions liên kết — lần thanh toán thực tế (1 đợt N lần)
    transaction_ids = fields.One2many(
        're.bank.guarantee.payment', 'schedule_id',
        string='Các lần thanh toán')
    transaction_count = fields.Integer(compute='_compute_transaction_count')

    # Computed paid + remaining + state
    amount_paid = fields.Monetary(
        string='Số tiền đã thanh toán',
        compute='_compute_paid', store=True)
    amount_remaining = fields.Monetary(
        string='Số tiền còn lại',
        compute='_compute_paid', store=True)
    state = fields.Selection(
        [('not_paid',     'Chưa thanh toán'),
         ('overdue',      'Quá hạn'),
         ('partial_paid', 'Thanh toán một phần'),
         ('fully_paid',   'Đã hoàn tất')],
        string='Trạng thái', compute='_compute_state', store=True)

    currency_id = fields.Many2one(
        related='guarantee_id.currency_id', store=True, readonly=True)
    company_id = fields.Many2one(
        related='guarantee_id.company_id', store=True, readonly=True)

    @api.depends('payment_kind', 'sequence')
    def _compute_name(self):
        kind_label = dict(self._fields['payment_kind'].selection)
        for rec in self:
            if not rec.name:
                seq = rec.sequence or 10
                rec.name = _("Đợt %s - %s") % (
                    seq // 10, kind_label.get(rec.payment_kind, ''))

    @api.depends('transaction_ids.amount', 'transaction_ids.state',
                 'amount_due')
    def _compute_paid(self):
        for rec in self:
            paid = sum(
                rec.transaction_ids.filtered(lambda t: t.state == 'posted')
                .mapped('amount'))
            rec.amount_paid = paid
            rec.amount_remaining = max(0.0, rec.amount_due - paid)

    @api.depends('amount_paid', 'amount_remaining', 'due_date', 'amount_due')
    def _compute_state(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.amount_remaining <= 0.01 and rec.amount_paid > 0:
                rec.state = 'fully_paid'
            elif rec.amount_paid > 0:
                rec.state = 'partial_paid'
            elif rec.due_date and rec.due_date < today:
                rec.state = 'overdue'
            else:
                rec.state = 'not_paid'

    @api.depends('transaction_ids')
    def _compute_transaction_count(self):
        for rec in self:
            rec.transaction_count = len(rec.transaction_ids)

    @api.constrains('amount_due')
    def _check_amount_due(self):
        for rec in self:
            if rec.amount_due <= 0:
                raise ValidationError(_(
                    "Số tiền phải trả của đợt phải > 0."))

    # Action button "Thanh toán" — mở wizard tạo transaction mới
    def action_open_pay(self):
        self.ensure_one()
        if not isinstance(self.id, int):
            raise UserError(_(
                "Đợt thanh toán chưa được lưu — bấm Lưu (Ctrl+S) "
                "Chứng thư trước khi ghi nhận thanh toán."))
        if self.amount_remaining <= 0.01:
            raise UserError(_(
                "Đợt này đã thanh toán đủ. Không cần tạo lần thanh "
                "toán mới."))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Ghi nhận thanh toán'),
            'res_model': 're.bank.guarantee.payment',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_guarantee_id': self.guarantee_id.id,
                'default_schedule_id': self.id,
                'default_payment_kind': self.payment_kind,
                'default_amount': self.amount_remaining,
                'default_name': _("TT %s") % (self.name or ''),
            },
        }

    def action_view_transactions(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Các lần thanh toán — %s') % self.name,
            'res_model': 're.bank.guarantee.payment',
            'view_mode': 'list,form',
            'domain': [('schedule_id', '=', self.id)],
            'context': {
                'default_guarantee_id': self.guarantee_id.id,
                'default_schedule_id': self.id,
                'default_payment_kind': self.payment_kind,
            },
        }


class ReBankGuaranteePayment(models.Model):
    _name = 're.bank.guarantee.payment'
    _description = 'Lần thanh toán Chứng thư BL (transaction)'
    _order = 'date desc, id desc'

    guarantee_id = fields.Many2one(
        're.bank.guarantee', string='Chứng thư BL',
        required=True, ondelete='cascade')
    schedule_id = fields.Many2one(
        're.bank.guarantee.payment.schedule',
        string='Đợt thanh toán', ondelete='set null',
        help='Đợt thanh toán mà lần này thuộc về. '
             'Có thể để trống nếu là thanh toán ngoài kế hoạch.')
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
    bank_account_id = fields.Many2one(
        'res.partner.bank', string='Tài khoản chuyển tiền',
        domain="[('partner_id', '=', company_partner_id)]",
        help='Tài khoản NH của doanh nghiệp dùng để thanh toán đợt '
             'này (khách hàng #16). Chỉ hiện TK của công ty hiện tại.')
    company_partner_id = fields.Many2one(
        'res.partner', related='company_id.partner_id',
        string='Đối tác công ty', readonly=True)
    reference = fields.Char(string='Số chứng từ NH')
    state = fields.Selection(
        [('draft',  'Nháp'),
         ('posted', 'Đã xác nhận')],
        string='Trạng thái', default='posted', required=True)

    # Phiếu chi thật trong sổ kế toán (backlog 969). Trước đây mỗi lần
    # trả tiền cho NH chỉ nằm ở bảng riêng này — tiền ra khỏi công ty
    # mà sổ cái không biết gì.
    payment_id = fields.Many2one(
        'account.payment', string='Phiếu chi', readonly=True, copy=False,
        ondelete='set null',
        help='Phiếu chi (outgoing payment) sinh từ đợt thanh toán này. '
             'Bấm vào để xem bút toán.')

    currency_id = fields.Many2one(
        related='guarantee_id.currency_id', store=True, readonly=True)
    company_id = fields.Many2one(
        related='guarantee_id.company_id', store=True, readonly=True)

    @api.onchange('company_id')
    def _onchange_company_default_bank(self):
        for rec in self:
            if not rec.bank_account_id and rec.company_id.partner_id:
                banks = rec.company_id.partner_id.bank_ids
                rec.bank_account_id = banks[:1] if banks else False

    @api.onchange('schedule_id')
    def _onchange_schedule_fill_guarantee(self):
        """Fill Chứng thư từ Đợt — fix ValidationError 'Missing
        guarantee_id' khi dialog thanh toán mở từ dòng lịch mới gen
        (context default bị NewId → False)."""
        for rec in self:
            if rec.schedule_id and not rec.guarantee_id:
                rec.guarantee_id = rec.schedule_id.guarantee_id

    @api.constrains('amount')
    def _check_amount(self):
        for rec in self:
            if rec.amount <= 0:
                raise ValidationError(_(
                    "Số tiền thanh toán phải > 0."))

    @api.constrains('schedule_id', 'guarantee_id', 'payment_kind')
    def _check_schedule_consistency(self):
        for rec in self:
            if rec.schedule_id:
                if rec.schedule_id.guarantee_id != rec.guarantee_id:
                    raise ValidationError(_(
                        "Đợt thanh toán phải thuộc cùng chứng thư BL."))
                if rec.schedule_id.payment_kind != rec.payment_kind:
                    raise ValidationError(_(
                        "Loại thanh toán phải khớp với loại của đợt."))

    @api.model_create_multi
    def create(self, vals_list):
        # Defensive: thiếu guarantee_id nhưng có schedule_id → fill
        # từ schedule (fix dialog thanh toán từ dòng lịch chưa lưu —
        # default_guarantee_id context = False).
        Schedule = self.env['re.bank.guarantee.payment.schedule']
        for vals in vals_list:
            if not vals.get('guarantee_id') and vals.get('schedule_id'):
                vals['guarantee_id'] = Schedule.browse(
                    vals['schedule_id']).guarantee_id.id
        recs = super().create(vals_list)
        recs._sync_account_payment()
        recs.guarantee_id._check_auto_settle()
        return recs

    def write(self, vals):
        res = super().write(vals)
        if 'state' in vals:
            self._sync_account_payment()
        self.guarantee_id._check_auto_settle()
        return res

    # ------------------------------------------------------------------
    # Phiếu chi kế toán (backlog 969)
    # ------------------------------------------------------------------
    def _payment_journal(self):
        """Sổ nhật ký cho phiếu chi.

        Ưu tiên sổ gắn đúng TÀI KHOẢN CHUYỂN TIỀN đã khai trên đợt
        thanh toán — đó là thông tin cụ thể nhất và người dùng đã khai
        sẵn. Không tìm được mới rơi về sổ mặc định trong cấu hình.
        """
        self.ensure_one()
        Journal = self.env['account.journal']
        if self.bank_account_id:
            journal = Journal.search([
                ('type', '=', 'bank'),
                ('bank_account_id', '=', self.bank_account_id.id),
                ('company_id', '=', self.company_id.id),
            ], limit=1)
            if journal:
                return journal
        journal = self.env['res.config.settings'].sudo(
        )._guarantee_payment_journal()
        if journal and journal.company_id == self.company_id:
            return journal
        return Journal.search([
            ('type', '=', 'bank'), ('company_id', '=', self.company_id.id),
        ], limit=1)

    def _sync_account_payment(self):
        """Sinh phiếu chi cho các đợt ĐÃ XÁC NHẬN chưa có phiếu.

        Chỉ chạy khi state='posted': đợt còn Nháp là hồ sơ đang soạn,
        chưa có tiền ra.

        KHÔNG chặn nếu chưa cấu hình tài khoản — ghi một dòng nhắc vào
        nhật ký chứng thư rồi thôi. Người nhập liệu đang ghi nhận một
        giao dịch ĐÃ XẢY RA ở ngân hàng; chặn họ lại vì kế toán chưa
        khai tài khoản chỉ làm mất luôn cả bản ghi.
        """
        Settings = self.env['res.config.settings'].sudo()
        kinds = dict(self._fields['payment_kind'].selection)
        for rec in self:
            if rec.state != 'posted' or rec.payment_id:
                continue
            account = Settings._guarantee_payment_account(rec.payment_kind)
            journal = rec._payment_journal()
            if not account or not journal:
                rec.guarantee_id.message_post(body=_(
                    "Đợt thanh toán %(k)s %(a)s ₫ ngày %(d)s CHƯA sinh "
                    "được phiếu chi: %(why)s. Khai xong rồi bấm \"Tạo "
                    "phiếu chi\" trên dòng đó.",
                    k=kinds.get(rec.payment_kind, rec.payment_kind),
                    a='{:,.0f}'.format(rec.amount or 0.0),
                    d=rec.date,
                    why=_("chưa khai tài khoản đối ứng") if not account
                    else _("chưa có sổ nhật ký chi")))
                continue
            rec._create_account_payment(account, journal)

    def _create_account_payment(self, account, journal):
        self.ensure_one()
        kinds = dict(self._fields['payment_kind'].selection)
        # clean_context: ngữ cảnh đang mang các khoá `default_*` của
        # CHÍNH bản ghi đợt thanh toán (vd default_name = "TT Đợt 4 —
        # Phí BL ..."). Không lọc thì Odoo áp luôn default_name lên
        # account.payment, và SỐ PHIẾU CHI thành câu diễn giải đó thay
        # vì số theo sổ nhật ký — sổ quỹ mất số chứng từ.
        payment = self.env['account.payment'].with_context(
            clean_context(self.env.context)).create({
            'payment_type': 'outbound',
            'partner_type': 'supplier',
            'partner_id': self.guarantee_id.issuing_bank_partner_id.id
            or self.guarantee_id.bank_partner_id.id,
            'amount': self.amount,
            'date': self.date,
            'journal_id': journal.id,
            'destination_account_id': account.id,
            'memo': _("%(k)s — BL %(g)s%(r)s",
                      k=kinds.get(self.payment_kind, self.payment_kind),
                      g=self.guarantee_id.name or '',
                      r=' · %s' % self.reference if self.reference else ''),
            'guarantee_payment_id': self.id,
        })
        payment.action_post()
        self.payment_id = payment
        self.guarantee_id.message_post(body=_(
            "Đã sinh phiếu chi %(p)s — %(k)s %(a)s ₫, hạch toán vào "
            "%(acc)s.",
            p=payment.name, k=kinds.get(self.payment_kind,
                                        self.payment_kind),
            a='{:,.0f}'.format(self.amount or 0.0),
            acc=account.display_name))
        return payment

    def action_create_payment(self):
        """Tạo phiếu chi cho dòng chưa có (vd lúc ghi nhận chưa khai TK)."""
        for rec in self:
            if rec.payment_id:
                raise UserError(_(
                    "Đợt thanh toán này đã có phiếu chi %s.",
                    rec.payment_id.name))
            if rec.state != 'posted':
                raise UserError(_(
                    "Đợt thanh toán còn Nháp — xác nhận trước đã."))
            kinds = dict(rec._fields['payment_kind'].selection)
            account = self.env['res.config.settings'].sudo(
            )._require_guarantee_account(
                rec.payment_kind, kinds.get(rec.payment_kind, ''))
            journal = rec._payment_journal()
            if not journal:
                raise UserError(_(
                    "Chưa có sổ nhật ký ngân hàng để ghi phiếu chi. "
                    "Khai \"Tài khoản chuyển tiền\" trên đợt thanh "
                    "toán, hoặc đặt sổ mặc định ở Vay > Cấu hình."))
            rec._create_account_payment(account, journal)

    def action_view_payment(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Phiếu chi'),
            'res_model': 'account.payment',
            'res_id': self.payment_id.id,
            'view_mode': 'form',
        }


class ReBankGuaranteeExpiryReminder(models.Model):
    """Nhắc người phụ trách khi chứng thư bảo lãnh sắp hết hạn.

    Số ngày nhắc trước và khoảng lặp lại để CẤU HÌNH chứ không chôn
    cứng: bảo lãnh thực hiện hợp đồng hai năm và bảo lãnh tạm ứng ba
    tháng không thể cùng một nhịp nhắc, và mỗi doanh nghiệp có thói
    quen xử lý gia hạn sớm muộn khác nhau.
    """
    _inherit = 're.bank.guarantee'

    last_expiry_reminder = fields.Date(
        string='Lần nhắc hết hạn gần nhất', readonly=True, copy=False)

    @api.model
    def _cron_expiry_reminder(self):
        Param = self.env['ir.config_parameter'].sudo()
        try:
            lead = int(Param.get_param('re_guarantee.expiry_lead_days', 30))
        except (TypeError, ValueError):
            lead = 30
        try:
            repeat = int(Param.get_param('re_guarantee.expiry_repeat_days', 7))
        except (TypeError, ValueError):
            repeat = 7

        today = fields.Date.context_today(self)
        limit = today + timedelta(days=lead)
        due = self.search([
            ('state', 'in', ('issued', 'extended')),
            ('date_expiry', '!=', False),
            ('date_expiry', '<=', limit),
            ('pic_user_id', '!=', False),
        ])
        template = self.env.ref(
            're_guarantee.mail_template_guarantee_expiry',
            raise_if_not_found=False)
        sent = 0
        for rec in due:
            # Đã nhắc rồi thì chờ hết khoảng lặp mới nhắc lại. Không có
            # chốt này thì mỗi sáng một thư cho tới ngày hết hạn.
            if rec.last_expiry_reminder:
                if (today - rec.last_expiry_reminder).days < repeat:
                    continue
            if template:
                template.send_mail(rec.id, force_send=False)
            rec.message_post(
                body=_('Bảo lãnh hết hạn ngày %(d)s — còn %(n)s ngày. '
                       'Đã gửi thư nhắc cho %(u)s.',
                       d=rec.date_expiry,
                       n=(rec.date_expiry - today).days,
                       u=rec.pic_user_id.name),
                partner_ids=rec.pic_user_id.partner_id.ids)
            rec.last_expiry_reminder = today
            sent += 1
        return sent
