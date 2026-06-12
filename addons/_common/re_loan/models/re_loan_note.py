# -*- coding: utf-8 -*-
"""
Khế ước nhận nợ (KW) — Promissory Note / Drawdown. Entity LÕI.

Mỗi lần rút vốn trong một hạn mức (facility) tạo một KW với số tiền, lãi suất,
kỳ hạn riêng. KW có dư nợ gốc, được giải ngân và trả nợ theo thời gian.

Phase L1b: giải ngân + trả nợ + lifecycle + nối hạn mức. Lịch lãi tự động,
phụ lục (L2), vay nội bộ (L4) bổ sung sau.
"""
from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class ReLoanNote(models.Model):
    _name = 're.loan.note'
    _description = 'Khế ước nhận nợ (KW)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_note desc, id desc'

    name = fields.Char(
        string='Số khế ước', required=True, copy=False, tracking=True,
        help='Số khế ước nhận nợ do ngân hàng cấp (nhập tay).')

    loan_type = fields.Selection(
        [('external', 'Vay ngân hàng'),
         ('onlending', 'Cho vay lại (nội bộ)')],
        string='Loại khoản vay', default='external', required=True,
        tracking=True)

    # external: rút trong hạn mức ngân hàng
    facility_id = fields.Many2one(
        're.loan.facility', string='Hạn mức', ondelete='restrict',
        tracking=True, help='Bắt buộc với khoản vay ngân hàng.')
    facility_type = fields.Selection(
        related='facility_id.facility_type', store=True, readonly=True,
        string='Loại facility')

    # onlending: cho công ty con vay lại từ một KW vay ngân hàng
    source_note_id = fields.Many2one(
        're.loan.note', string='KW nguồn (vay NH)', ondelete='restrict',
        domain="[('loan_type','=','external')]",
        help='Khế ước vay ngân hàng tài trợ cho khoản cho vay lại này.')
    counterparty_id = fields.Many2one(
        'res.partner', string='Bên vay (công ty con)',
        domain="[('is_company','=',True)]")
    onlending_ids = fields.One2many(
        're.loan.note', 'source_note_id', string='Khoản cho vay lại')
    amount_onlent = fields.Monetary(
        string='Đã cho vay lại', compute='_compute_amount_onlent', store=True,
        help='Tổng số tiền các khoản cho vay lại từ KW này.')

    # Liên kết (computed để hỗ trợ cả external + onlending)
    credit_contract_id = fields.Many2one(
        're.loan.credit.contract', string='HĐTD',
        compute='_compute_links', store=True)
    partner_id = fields.Many2one(
        'res.partner', string='Đối tác',
        compute='_compute_links', store=True,
        help='Ngân hàng (vay NH) hoặc công ty con (cho vay lại).')
    company_id = fields.Many2one(
        'res.company', compute='_compute_links', store=True)
    currency_id = fields.Many2one(
        'res.currency', compute='_compute_links', store=True)

    date_note = fields.Date(
        string='Ngày nhận nợ', required=True,
        default=fields.Date.context_today, tracking=True)
    amount = fields.Monetary(
        string='Số tiền KW', required=True, tracking=True,
        help='Số tiền cam kết của KW. Khi user thêm/sửa giải ngân, '
             'field này tự = Σ số tiền các dòng giải ngân (onchange). '
             'User vẫn override tay được nếu cần.')
    interest_rate = fields.Float(
        string='Lãi suất (%/năm)', digits=(5, 2), tracking=True,
        aggregator=None,
        help='Lãi suất KÝ BAN ĐẦU của KW — IMMUTABLE sau khi áp dụng '
             'phụ lục đổi rate. Lịch sử thay đổi rate xem ở tab "Phụ '
             'lục". Rate hiệu lực hiện tại = phụ lục rate mới nhất đã '
             'áp dụng (nếu có), fallback chính field này.')
    interest_method = fields.Selection(
        [('declining', 'Dư nợ giảm dần'),
         ('flat', 'Cố định trên gốc ban đầu')],
        string='Phương pháp tính lãi', default='declining', required=True)
    day_count = fields.Selection(
        [('act_365', 'Thực tế / 365'),
         ('act_360', 'Thực tế / 360'),
         ('30_360', '30 / 360')],
        string='Quy ước ngày tính lãi', default='act_360', required=True)

    tenor_months = fields.Integer(string='Kỳ hạn (tháng)', aggregator=None)
    date_maturity = fields.Date(
        string='Ngày đáo hạn', compute='_compute_date_maturity',
        store=True, readonly=False, tracking=True,
        help='Tự tính = ngày nhận nợ + kỳ hạn; có thể sửa tay.')
    repayment_plan = fields.Selection(
        [('bullet', 'Trả gốc cuối kỳ (Bullet)'),
         ('equal_principal', 'Trả gốc đều'),
         ('custom', 'Tuỳ chỉnh')],
        string='Kế hoạch trả gốc', default='bullet')
    purpose = fields.Text(string='Mục đích sử dụng vốn')

    state = fields.Selection(
        [('draft', 'Nháp'),
         ('sent_to_bank', 'Đã gửi NH'),
         ('active', 'Hiệu lực'),
         ('partial_paid', 'Trả một phần'),
         ('fully_paid', 'Đã tất toán'),
         ('overdue', 'Quá hạn'),
         ('restructured', 'Đã cơ cấu'),
         ('cancelled', 'Đã huỷ')],
        string='Trạng thái', default='draft', required=True, tracking=True)

    disbursement_ids = fields.One2many(
        're.loan.note.disbursement', 'note_id', string='Giải ngân')
    repayment_ids = fields.One2many(
        're.loan.note.repayment', 'note_id', string='Trả nợ')
    interest_line_ids = fields.One2many(
        're.loan.note.interest.line', 'note_id', string='Lịch lãi')
    interest_total_planned = fields.Monetary(
        string='Tổng lãi dự kiến', compute='_compute_interest_total',
        store=True)
    amendment_ids = fields.One2many(
        're.loan.note.amendment', 'note_id', string='Phụ lục')
    amendment_count = fields.Integer(
        string='Số phụ lục', compute='_compute_amendment_count')
    # Pledge gắn DIRECTLY vào KW này (target='note', hiếm)
    direct_pledge_ids = fields.One2many(
        're.loan.collateral.pledge', 'note_id',
        string='TSBĐ gắn riêng KW',
        domain="[('pledge_target', '=', 'note')]",
        help='Hiếm — vay từng lần có TSBĐ riêng. Đa số dùng pledge cấp '
             'HĐTD/Facility, KW kế thừa qua all_pledge_ids.')
    # TẤT CẢ pledge áp dụng cho KW này: own + facility + contract
    all_pledge_ids = fields.Many2many(
        're.loan.collateral.pledge', string='Tất cả TSBĐ áp dụng',
        compute='_compute_all_pledges',
        help='Pledge từ HĐTD (kế thừa) + Facility (kế thừa) + KW (riêng).')
    pledge_count = fields.Integer(compute='_compute_all_pledges')

    @api.depends('facility_id', 'facility_id.pledge_ids',
                 'facility_id.credit_contract_id.pledge_ids',
                 'direct_pledge_ids')
    def _compute_all_pledges(self):
        for rec in self:
            pledges = rec.direct_pledge_ids
            if rec.facility_id:
                pledges |= rec.facility_id.pledge_ids
                if rec.facility_id.credit_contract_id:
                    pledges |= rec.facility_id.credit_contract_id.pledge_ids
            rec.all_pledge_ids = pledges
            rec.pledge_count = len(pledges)

    amount_disbursed = fields.Monetary(
        string='Đã giải ngân', compute='_compute_amounts', store=True)
    amount_repaid_principal = fields.Monetary(
        string='Đã trả gốc', compute='_compute_amounts', store=True)
    amount_repaid_interest = fields.Monetary(
        string='Đã trả lãi', compute='_compute_amounts', store=True)
    principal_outstanding = fields.Monetary(
        string='Dư nợ gốc', compute='_compute_amounts', store=True,
        help='= Số tiền KW − Đã trả gốc. Theo nghiệp vụ VN: KW ký nhận '
             'nợ toàn bộ số tiền cam kết; dư nợ giảm dần khi trả gốc. '
             'Lưu ý: nếu đã giải ngân không đủ số tiền KW, vẫn tính '
             'theo cam kết — disbursement chỉ tracking dòng tiền thực.')
    interest_outstanding = fields.Monetary(
        string='Dư nợ lãi',
        compute='_compute_interest_outstanding', store=True,
        help='= Tổng lãi dự kiến − Đã trả lãi.')
    total_outstanding = fields.Monetary(
        string='Tổng dư nợ (gốc + lãi)',
        compute='_compute_interest_outstanding', store=True,
        help='= Dư nợ gốc + Dư nợ lãi.')

    @api.depends('interest_total_planned', 'amount_repaid_interest',
                 'principal_outstanding')
    def _compute_interest_outstanding(self):
        for rec in self:
            rec.interest_outstanding = (
                rec.interest_total_planned - rec.amount_repaid_interest)
            rec.total_outstanding = (
                rec.principal_outstanding + rec.interest_outstanding)

    is_overdue = fields.Boolean(
        string='Quá hạn?', compute='_compute_is_overdue')
    days_overdue = fields.Integer(
        string='Số ngày quá hạn', compute='_compute_is_overdue')
    aging_bucket = fields.Selection(
        [('current', 'Trong hạn'),
         ('b1_30', 'Quá hạn 1-30 ngày'),
         ('b31_60', 'Quá hạn 31-60 ngày'),
         ('b61_90', 'Quá hạn 61-90 ngày'),
         ('b91_180', 'Quá hạn 91-180 ngày'),
         ('b181_365', 'Quá hạn 181-365 ngày'),
         ('b365', 'Quá hạn > 365 ngày')],
        string='Nhóm tuổi nợ', compute='_compute_aging_bucket', store=True,
        help='Phân nhóm tuổi nợ theo số ngày quá hạn. Refresh hằng ngày '
             'bằng cron.')

    # ------------------------------------------------------------------
    # Tiến độ thanh toán (Báo cáo 5) — compute non-stored theo today
    # ------------------------------------------------------------------
    principal_due_to_date = fields.Monetary(
        string='Gốc đến hạn (luỹ kế)', compute='_compute_payment_progress',
        help='Tổng gốc đáng lẽ phải trả tính đến hôm nay theo kế hoạch.')
    interest_due_to_date = fields.Monetary(
        string='Lãi đến hạn (luỹ kế)', compute='_compute_payment_progress',
        help='Tổng lãi đến hạn theo lịch lãi (date_to ≤ today).')
    principal_variance = fields.Monetary(
        string='Chênh lệch gốc', compute='_compute_payment_progress',
        help='Đã trả gốc − Gốc đến hạn. Âm = chậm, dương = vượt KH.')
    interest_variance = fields.Monetary(
        string='Chênh lệch lãi', compute='_compute_payment_progress',
        help='Đã trả lãi − Lãi đến hạn.')

    note = fields.Text(string='Ghi chú')
    active = fields.Boolean(default=True)

    # ------------------------------------------------------------------
    # Compute
    # ------------------------------------------------------------------
    @api.depends('date_note', 'tenor_months')
    def _compute_date_maturity(self):
        for rec in self:
            if rec.date_note and rec.tenor_months:
                rec.date_maturity = rec.date_note + relativedelta(
                    months=rec.tenor_months)
            elif not rec.date_maturity:
                rec.date_maturity = False

    @api.depends('amount', 'disbursement_ids.amount',
                 'repayment_ids.amount_principal',
                 'repayment_ids.amount_interest')
    def _compute_amounts(self):
        for rec in self:
            rec.amount_disbursed = sum(rec.disbursement_ids.mapped('amount'))
            rec.amount_repaid_principal = sum(
                rec.repayment_ids.mapped('amount_principal'))
            rec.amount_repaid_interest = sum(
                rec.repayment_ids.mapped('amount_interest'))
            # Dư nợ gốc = Số tiền KW − Đã trả gốc
            # (theo nghiệp vụ VN: KW ký → nhận nợ toàn bộ; trả gốc giảm dần)
            rec.principal_outstanding = (
                rec.amount - rec.amount_repaid_principal)

    @api.depends('interest_line_ids.interest_amount')
    def _compute_interest_total(self):
        for rec in self:
            rec.interest_total_planned = sum(
                rec.interest_line_ids.mapped('interest_amount'))

    @api.depends('amendment_ids')
    def _compute_amendment_count(self):
        for rec in self:
            rec.amendment_count = len(rec.amendment_ids)

    @api.depends('loan_type', 'facility_id', 'facility_id.credit_contract_id',
                 'source_note_id', 'counterparty_id')
    def _compute_links(self):
        default_company = self.env.company
        for rec in self:
            if rec.loan_type == 'onlending':
                src = rec.source_note_id
                rec.credit_contract_id = src.credit_contract_id.id \
                    if src else False
                rec.company_id = (src.company_id.id if src and src.company_id
                                  else default_company.id)
                rec.currency_id = (
                    src.currency_id.id if src and src.currency_id
                    else default_company.currency_id.id)
                rec.partner_id = rec.counterparty_id.id
            else:
                fac = rec.facility_id
                rec.credit_contract_id = fac.credit_contract_id.id \
                    if fac else False
                rec.company_id = (fac.company_id.id if fac and fac.company_id
                                  else default_company.id)
                rec.currency_id = (
                    fac.currency_id.id if fac and fac.currency_id
                    else default_company.currency_id.id)
                rec.partner_id = (
                    fac.credit_contract_id.partner_id.id
                    if fac and fac.credit_contract_id else False)

    @api.depends('onlending_ids.amount', 'onlending_ids.state')
    def _compute_amount_onlent(self):
        for rec in self:
            rec.amount_onlent = sum(rec.onlending_ids.filtered(
                lambda n: n.state != 'cancelled').mapped('amount'))

    @api.depends('date_maturity', 'principal_outstanding', 'state')
    def _compute_is_overdue(self):
        today = fields.Date.context_today(self)
        for rec in self:
            overdue = bool(
                rec.date_maturity
                and rec.state in ('active', 'partial_paid', 'overdue')
                and rec.principal_outstanding > 0
                and rec.date_maturity < today)
            rec.is_overdue = overdue
            rec.days_overdue = (today - rec.date_maturity).days \
                if overdue else 0

    @api.depends('repayment_plan', 'date_note', 'date_maturity', 'amount',
                 'tenor_months', 'interest_line_ids.interest_amount',
                 'interest_line_ids.date_to', 'amount_repaid_principal',
                 'amount_repaid_interest')
    def _compute_payment_progress(self):
        today = fields.Date.context_today(self)
        for rec in self:
            # Lãi đến hạn = Σ interest_line.interest_amount where date_to ≤ today
            rec.interest_due_to_date = sum(
                line.interest_amount for line in rec.interest_line_ids
                if line.date_to and line.date_to <= today)
            # Gốc đến hạn theo repayment_plan
            if rec.repayment_plan == 'equal_principal' \
                    and rec.tenor_months and rec.date_note:
                elapsed = max(0,
                    (today.year - rec.date_note.year) * 12
                    + (today.month - rec.date_note.month))
                elapsed = min(elapsed, rec.tenor_months)
                rec.principal_due_to_date = (
                    rec.amount * elapsed / rec.tenor_months
                    if rec.tenor_months else 0.0)
            elif rec.repayment_plan == 'bullet':
                rec.principal_due_to_date = (
                    rec.amount
                    if (rec.date_maturity and rec.date_maturity <= today)
                    else 0.0)
            else:
                # custom: chưa model được lịch trả gốc → 0
                rec.principal_due_to_date = 0.0
            rec.principal_variance = (
                rec.amount_repaid_principal - rec.principal_due_to_date)
            rec.interest_variance = (
                rec.amount_repaid_interest - rec.interest_due_to_date)

    @api.depends('principal_outstanding', 'date_maturity', 'state')
    def _compute_aging_bucket(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.principal_outstanding <= 0 \
                    or rec.state in ('draft', 'cancelled', 'fully_paid'):
                rec.aging_bucket = False
            elif not rec.date_maturity or rec.date_maturity >= today:
                rec.aging_bucket = 'current'
            else:
                d = (today - rec.date_maturity).days
                if d <= 30:
                    rec.aging_bucket = 'b1_30'
                elif d <= 60:
                    rec.aging_bucket = 'b31_60'
                elif d <= 90:
                    rec.aging_bucket = 'b61_90'
                elif d <= 180:
                    rec.aging_bucket = 'b91_180'
                elif d <= 365:
                    rec.aging_bucket = 'b181_365'
                else:
                    rec.aging_bucket = 'b365'

    # ------------------------------------------------------------------
    # Onchange: tự đồng bộ Số tiền KW = Σ số tiền giải ngân
    # ------------------------------------------------------------------
    @api.onchange('disbursement_ids')
    def _onchange_disbursement_sum_amount(self):
        """Khi user thêm/sửa/xóa giải ngân, Số tiền KW tự = Σ giải ngân.
        User vẫn override tay được sau đó nhưng lần edit giải ngân tiếp
        theo sẽ overwrite.
        """
        if self.disbursement_ids:
            self.amount = sum(self.disbursement_ids.mapped('amount'))

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------
    @api.constrains('amount', 'state')
    def _check_amount(self):
        """KW state='draft' cho phép amount=0 (user mới tạo, chưa
        nhập giải ngân). State khác bắt buộc amount > 0.
        Mọi state không cho phép amount âm.
        """
        for rec in self:
            if rec.amount < 0:
                raise ValidationError(_("Số tiền KW không được âm."))
            if rec.state != 'draft' and rec.amount == 0:
                raise ValidationError(_(
                    "Số tiền KW phải lớn hơn 0 trước khi gửi NH / "
                    "kích hoạt."))

    def _facility_contribution(self):
        """Phần KW này hiện đang chiếm 'amount_used' của facility.

        - Draft/Cancelled: 0 (chưa tính vào used)
        - Revolving / Overdraft: dư nợ gốc còn lại
        - Term / Bảo lãnh / L/C: số tiền KW cam kết
        """
        self.ensure_one()
        if self.state in ('draft', 'cancelled') or not self.facility_id:
            return 0.0
        if self.facility_id.facility_type in ('revolving', 'overdraft'):
            return self.principal_outstanding
        return self.amount

    @api.constrains('amount', 'facility_id', 'state', 'loan_type')
    def _check_amount_within_facility(self):
        """KW không được nhập amount vượt 'Còn lại' của facility.

        - Chỉ áp dụng cho loan_type='external' (vay NH có facility).
        - Cho phép đúng giới hạn còn lại + phần KW này đang chiếm
          (để có thể edit KW đang active mà không bị self-reject).
        """
        for rec in self:
            if rec.loan_type != 'external' or not rec.facility_id:
                continue
            if rec.state == 'cancelled':
                continue
            facility = rec.facility_id
            own_contribution = rec._facility_contribution()
            # amount_available đã trừ own_contribution (vì rec đang
            # trong facility.note_ids). Cộng lại để có "hạn mức tối
            # đa rec có thể chiếm" — tránh constraint tự reject khi
            # user chỉ edit field khác.
            max_amount = facility.amount_available + own_contribution
            # Tolerance 1đ tránh lỗi rounding cho VND.
            if rec.amount > max_amount + 1:
                raise ValidationError(_(
                    "Số tiền KW (%(a)s) vượt hạn mức còn lại của "
                    "facility '%(f)s' (%(m)s). Tăng hạn mức facility, "
                    "trả bớt KW khác, hoặc giảm số tiền KW này.",
                    a=rec.amount, f=facility.name, m=max_amount))

    @api.constrains('loan_type', 'facility_id', 'source_note_id',
                    'counterparty_id')
    def _check_loan_type_targets(self):
        for rec in self:
            if rec.loan_type == 'external' and not rec.facility_id:
                raise ValidationError(_(
                    "Khoản vay ngân hàng cần chọn Hạn mức (facility)."))
            if rec.loan_type == 'onlending':
                if not rec.source_note_id:
                    raise ValidationError(_(
                        "Khoản cho vay lại cần chọn KW nguồn (vay NH)."))
                if not rec.counterparty_id:
                    raise ValidationError(_(
                        "Khoản cho vay lại cần chọn Bên vay (công ty con)."))
                if rec.source_note_id.loan_type != 'external':
                    raise ValidationError(_(
                        "KW nguồn phải là khoản vay ngân hàng."))

    @api.constrains('amount', 'source_note_id', 'loan_type')
    def _check_onlending_total(self):
        for rec in self:
            if rec.loan_type != 'onlending' or not rec.source_note_id:
                continue
            src = rec.source_note_id
            total = sum(src.onlending_ids.filtered(
                lambda n: n.state != 'cancelled').mapped('amount'))
            if total > src.amount:
                raise ValidationError(_(
                    "Tổng cho vay lại (%(t)s) vượt số tiền KW nguồn "
                    "'%(n)s' (%(a)s).",
                    t=total, n=src.name, a=src.amount))

    # ------------------------------------------------------------------
    # State machine
    # ------------------------------------------------------------------
    def action_send_to_bank(self):
        """Gửi hồ sơ KW lên NH duyệt. draft → sent_to_bank."""
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_(
                    "Chỉ gửi NH được khi KW đang ở trạng thái Nháp."))
            if rec.amount <= 0:
                raise UserError(_(
                    "Số tiền KW phải > 0 trước khi gửi NH."))
            rec.state = 'sent_to_bank'
            rec.message_post(body=_(
                "Đã gửi hồ sơ KW '%(n)s' lên NH chờ duyệt.",
                n=rec.name or ''))

    def action_activate(self):
        for rec in self:
            # Cho phép kích hoạt từ Nháp (workflow rút gọn cũ) hoặc
            # từ Đã gửi NH (workflow chuẩn mới: NH duyệt → kích hoạt).
            if rec.state not in ('draft', 'sent_to_bank'):
                raise UserError(_(
                    "Chỉ kích hoạt được KW đang Nháp hoặc Đã gửi NH."))
            if not rec.date_maturity:
                raise UserError(_(
                    "Cần nhập Ngày đáo hạn (hoặc Kỳ hạn) trước khi kích hoạt."))
            if rec.loan_type == 'external':
                available = rec.facility_id.amount_available
                if rec.amount > available:
                    raise UserError(_(
                        "Số tiền KW (%(amt)s) vượt hạn mức còn lại của "
                        "facility '%(fac)s' (%(avail)s).",
                        amt=rec.amount, fac=rec.facility_id.name,
                        avail=available))
            else:  # onlending — cảnh báo lãi suất (BR-8)
                src = rec.source_note_id
                if src and rec.interest_rate < src.interest_rate:
                    rec.message_post(body=_(
                        "Cảnh báo: lãi suất cho vay lại (%(r)s%%) thấp hơn "
                        "lãi KW nguồn %(n)s (%(sr)s%%).",
                        r=rec.interest_rate, n=src.name,
                        sr=src.interest_rate))
            rec.state = 'active'
            # Tự sinh lịch lãi dự kiến nếu chưa có.
            if not rec.interest_line_ids:
                rec.action_generate_interest_schedule()
            # Auto-disbursed: khi KW kích hoạt, tất cả giải ngân chưa
            # đóng được đẩy sang 'Đã giải ngân' — chuẩn workflow VN: NH
            # ký KW = NH đã chuyển tiền các đợt giải ngân kèm hồ sơ.
            rec._auto_disburse_on_activate()

    def _auto_disburse_on_activate(self):
        """Khi KW activate, force toàn bộ disbursement chưa đóng → 'disbursed'.

        Bypass workflow draft → submitted → approved của
        re.loan.note.disbursement vì user request: "kích hoạt KW =
        chuyển TẤT CẢ giải ngân sang Đã giải ngân". Đặt
        date_bank_approved = today nếu chưa có (để lịch lãi tính từ
        ngày KW active).
        """
        today = fields.Date.context_today(self)
        for rec in self:
            pending = rec.disbursement_ids.filtered(
                lambda d: d.state not in ('disbursed', 'cancelled'))
            for disb in pending:
                if not disb.date_bank_approved:
                    disb.date_bank_approved = today
                # Force state = disbursed (không gọi action_disburse
                # vì nó yêu cầu state='approved').
                disb.state = 'disbursed'
                disb.message_post(body=_(
                    "Tự động chuyển 'Đã giải ngân' khi KW kích hoạt."))
            if pending:
                rec.message_post(body=_(
                    "Tự chuyển %(n)s giải ngân sang Đã giải ngân.",
                    n=len(pending)))

    def action_cancel(self):
        for rec in self:
            if rec.state in ('fully_paid',):
                raise UserError(_("Không thể huỷ KW đã tất toán."))
            if rec.amount_repaid_principal > 0:
                raise UserError(_(
                    "Không thể huỷ KW đã có phát sinh trả gốc."))
            rec.state = 'cancelled'

    def action_reset_draft(self):
        for rec in self:
            if rec.state not in ('cancelled', 'sent_to_bank'):
                raise UserError(_(
                    "Chỉ KW Đã huỷ hoặc Đã gửi NH mới rút về Nháp được."))
            rec.state = 'draft'

    def action_release_guarantee(self):
        """Giải tỏa Bảo lãnh / L/C — KW chuyển sang fully_paid.

        Áp dụng cho KW thuộc facility loại guarantee_line hoặc lc_line:
        khi NH trả lại chứng thư BL (CĐT bàn giao hoàn thành / hết hạn
        không gia hạn), không có dòng tiền trả gốc thực — chỉ đóng KW
        + giải phóng hạn mức bảo lãnh.
        """
        for rec in self:
            if rec.facility_id.facility_type not in (
                    'guarantee_line', 'lc_line'):
                raise UserError(_(
                    "Hành động này chỉ dùng cho KW thuộc Hạn mức bảo "
                    "lãnh hoặc Hạn mức L/C. Với KW vay thông thường, "
                    "dùng Trả nợ để tất toán."))
            if rec.state in ('fully_paid', 'cancelled'):
                raise UserError(_(
                    "KW '%s' đã đóng (state=%s).", rec.name, rec.state))
            rec.state = 'fully_paid'
            rec.message_post(body=_(
                "Đã giải tỏa Bảo lãnh/L/C — hạn mức %(amt)s khôi phục "
                "vào facility '%(fac)s'.",
                amt=rec.amount, fac=rec.facility_id.name))

    # ------------------------------------------------------------------
    # Lịch lãi (pluggable theo interest_method)
    # ------------------------------------------------------------------
    def action_generate_interest_schedule(self):
        """(Re)sinh lịch lãi dự kiến. Giữ lại dòng đã ghi nhận/đã trả,
        chỉ thay thế các dòng còn 'planned'."""
        for note in self:
            if note.state == 'cancelled':
                raise UserError(_(
                    "Không sinh lịch lãi cho KW đã huỷ."))
            note.interest_line_ids.filtered(
                lambda l: l.state == 'planned').unlink()
            vals = note._build_interest_schedule_lines()
            note.interest_line_ids = [(0, 0, v) for v in vals]
        return True

    def _effective_rate_at(self, dt):
        """Lãi suất hiệu lực vào ngày dt theo lịch sử phụ lục.

        Trả về:
          - new_interest_rate của phụ lục rate đã áp dụng có
            date_effective <= dt và mới nhất, NẾU có.
          - Nếu không có phụ lục nào áp dụng trước/đúng dt:
            self.interest_rate (giá trị ký ban đầu, immutable).

        Dùng để sinh lịch lãi đúng cho từng kỳ — kỳ trước phụ lục
        đầu tiên giữ lãi suất ký ban đầu, kỳ sau dùng lãi suất phụ lục.
        """
        self.ensure_one()
        applied = self.amendment_ids.filtered(
            lambda a: a.state == 'applied'
            and a.amendment_type == 'rate'
            and a.date_effective and a.date_effective <= dt)
        if applied:
            latest = applied.sorted('date_effective')[-1]
            return latest.new_interest_rate
        return self.interest_rate

    def _build_interest_schedule_lines(self):
        """Trả về list dict các dòng lịch lãi.

        Pluggable: override để thêm phương pháp mới (vd annuity / trả góp
        đều). Hiện hỗ trợ:
          - declining (dư nợ giảm dần): principal_base = dư nợ đầu kỳ
          - flat (cố định): principal_base = gốc ban đầu mọi kỳ
        Kế hoạch trả gốc (repayment_plan) quyết định dư nợ giảm thế nào:
          - bullet/custom: gốc giữ nguyên đến cuối kỳ
          - equal_principal: gốc giảm đều mỗi kỳ
        Lãi suất: lấy theo _effective_rate_at(date_from) — kỳ trước
        phụ lục đầu tiên giữ rate gốc, kỳ sau dùng rate phụ lục.
        """
        self.ensure_one()
        if not self.date_note:
            raise UserError(_("Cần Ngày nhận nợ để sinh lịch lãi."))
        principal = self.amount
        n = self.tenor_months or 0
        vals = []
        if n > 0:
            principal_per_period = (
                principal / n if self.repayment_plan == 'equal_principal'
                else 0.0)
            opening = principal
            date_cursor = self.date_note
            for i in range(1, n + 1):
                date_to = self.date_note + relativedelta(months=i)
                base = (principal if self.interest_method == 'flat'
                        else opening)
                vals.append({
                    'period_no': i,
                    'date_from': date_cursor,
                    'date_to': date_to,
                    'principal_base': base,
                    'interest_rate': self._effective_rate_at(date_cursor),
                })
                opening -= principal_per_period
                date_cursor = date_to
        elif self.date_maturity:
            vals.append({
                'period_no': 1,
                'date_from': self.date_note,
                'date_to': self.date_maturity,
                'principal_base': principal,
                'interest_rate': self._effective_rate_at(self.date_note),
            })
        else:
            raise UserError(_(
                "Cần Kỳ hạn hoặc Ngày đáo hạn để sinh lịch lãi."))
        return vals

    # ------------------------------------------------------------------
    # Auto state from payments (gọi bởi disbursement/repayment)
    # ------------------------------------------------------------------
    def _update_payment_state(self):
        """Auto cập nhật state KW theo repayments.

        - fully_paid: gốc trả hết (principal_outstanding <= 0). Chỉ
          quan tâm gốc — vì khi gốc về 0, lãi cũng không phát sinh tiếp.
        - partial_paid: ĐÃ CÓ phát sinh trả (gốc HOẶC lãi) > 0 — phản
          ánh nghiệp vụ trích thu tự động: NH có thể chỉ trích lãi
          trước, gốc trả cuối kỳ → KW phải hiện 'Trả 1 phần' chứ
          không giữ 'Hiệu lực'.
        - active: chưa có phát sinh trả nào.

        Skip states: draft, cancelled, restructured.
        """
        for rec in self:
            if rec.state in ('draft', 'cancelled', 'restructured'):
                continue
            has_repayment = (rec.amount_repaid_principal > 0
                             or rec.amount_repaid_interest > 0)
            if rec.amount_disbursed > 0 and rec.principal_outstanding <= 0:
                rec.state = 'fully_paid'
            elif has_repayment:
                rec.state = 'partial_paid'
            else:
                # Không có phát sinh trả → quay về active nếu đang
                # ở partial_paid/overdue (vd vừa unlink repayments).
                if rec.state in ('partial_paid', 'overdue'):
                    rec.state = 'active'

    # ------------------------------------------------------------------
    # Guards
    # ------------------------------------------------------------------
    def unlink(self):
        for rec in self:
            if rec.disbursement_ids or rec.repayment_ids:
                raise UserError(_(
                    "Không thể xoá KW '%s' đã có giải ngân/trả nợ. Huỷ thay "
                    "vì xoá để giữ vết.", rec.name))
        return super().unlink()

    # ------------------------------------------------------------------
    # Onchange tiện ích
    # ------------------------------------------------------------------
    @api.onchange('facility_id')
    def _onchange_facility_id(self):
        if self.facility_id:
            self.interest_rate = self.facility_id.interest_rate_default
            self.interest_method = self.facility_id.interest_method
            self.day_count = self.facility_id.day_count

    # ------------------------------------------------------------------
    # Cron
    # ------------------------------------------------------------------
    @api.model
    def _cron_update_loan_status(self):
        """Hằng ngày: đánh dấu KW quá hạn, hồi trạng thái nếu hết quá hạn,
        và refresh nhóm tuổi nợ (aging)."""
        today = fields.Date.context_today(self)
        live = self.search([
            ('state', 'in', ('active', 'partial_paid', 'overdue'))])
        for note in live:
            overdue = (note.principal_outstanding > 0 and note.date_maturity
                       and note.date_maturity < today)
            if overdue and note.state != 'overdue':
                note.state = 'overdue'
            elif not overdue and note.state == 'overdue':
                note._update_payment_state()
        # Refresh aging (phụ thuộc 'today' nên cần tính lại định kỳ).
        live._compute_aging_bucket()
        live.flush_recordset(['aging_bucket'])
        return True

    @api.model
    def _cron_maturity_reminder(self):
        """Tạo activity nhắc đáo hạn cho KW sắp đến hạn trong N ngày."""
        days = int(self.env['ir.config_parameter'].sudo().get_param(
            're_loan.reminder_days', 7))
        today = fields.Date.context_today(self)
        limit_date = today + timedelta(days=days)
        notes = self.search([
            ('state', 'in', ('active', 'partial_paid')),
            ('principal_outstanding', '>', 0),
            ('date_maturity', '>=', today),
            ('date_maturity', '<=', limit_date)])
        for note in notes:
            already = note.activity_ids.filtered(
                lambda a: a.summary == 'KW sắp đáo hạn')
            if already:
                continue
            note.activity_schedule(
                'mail.mail_activity_data_todo',
                date_deadline=note.date_maturity,
                summary='KW sắp đáo hạn',
                note=_('Khế ước %(name)s đáo hạn ngày %(d)s, dư nợ gốc %(o)s.',
                       name=note.name, d=note.date_maturity,
                       o=note.principal_outstanding),
                user_id=note.create_uid.id or self.env.uid)
        return True
