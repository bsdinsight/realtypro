# -*- coding: utf-8 -*-
"""
Đề nghị phát hành bảo lãnh — entity quản lý request BL trước khi NH
phát chứng thư.

Flow:
  draft → active → settled
                ↘ cancelled

  - draft     : nhập thông tin, chưa chiếm hạn mức facility
  - active    : đã kích hoạt — chiếm hạn mức facility, bắt đầu tính
                phí BL theo thời gian + phí phạt quá hạn (nếu trả chậm)
  - settled   : đã tất toán (đủ phí + ký quỹ + phạt) — KHÔI PHỤC hạn
                mức facility (compute amount_used loại bỏ settled)
  - cancelled : huỷ request từ nháp

Phí BL = giá trị BL × tỷ lệ phí (%/năm) × số ngày hiệu lực / 365
Phạt trả chậm = (phí + ký quỹ chưa trả) × tỷ lệ phạt (%/năm) × số
                ngày quá hạn / 365.

Khác `re.bank.guarantee`:
  - `re.bank.guarantee` = chứng thư NH đã phát hành (sau khi request được duyệt).
  - `re.guarantee.request` = đề nghị xin BL (entity gọn cho team
    track phí + thanh toán + tất toán).

Cả 2 có thể link với nhau qua field `bank_guarantee_id` (optional)
khi NH phát hành chứng thư chính thức.
"""
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


class ReGuaranteeRequest(models.Model):
    _name = 're.guarantee.request'
    _description = 'Đề nghị phát hành Bảo lãnh'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_request desc, id desc'

    name = fields.Char(
        string='Số đề nghị', required=True, copy=False, tracking=True,
        default=lambda self: _('/'),
        help='Auto sinh sequence ĐNBL/YYYY/NNNNN khi save.')
    guarantee_type = fields.Selection(
        GUARANTEE_TYPES, string='Loại BL', required=True, tracking=True,
        default='performance')

    # ------------------------------------------------------------------
    # Hạn mức — facility loại "Hạn mức bảo lãnh"
    # ------------------------------------------------------------------
    facility_id = fields.Many2one(
        're.loan.facility', string='Hạn mức bảo lãnh',
        required=True, tracking=True,
        # Lọc theo PHÂN LOẠI mục đích, không theo mã 'bank_guarantee'
        # cứng: từ backlog 730 người dùng khai thêm được mục đích và
        # chọn phân loại Bảo lãnh cho nó — khoá theo mã thì những mục
        # tự khai đó không bao giờ chọn được.
        domain="[('purpose_kind', '=', 'guarantee'),"
               " ('credit_contract_id.state', '=', 'active')]",
        help='Chỉ chọn được hạn mức có Mục đích thuộc nhóm "Bảo lãnh" '
             'và thuộc HĐTD đã kích hoạt. BL active sẽ chiếm hạn mức '
             '= giá trị BL; settled/cancelled không chiếm.')
    credit_contract_id = fields.Many2one(
        're.loan.credit.contract', string='HĐTD',
        related='facility_id.credit_contract_id',
        store=True, readonly=True)
    issuing_bank_partner_id = fields.Many2one(
        'res.partner', string='NH phát hành',
        related='credit_contract_id.partner_id',
        store=True, readonly=True)

    # ------------------------------------------------------------------
    # Bên thụ hưởng + Áp dụng cho công trình / HĐ NT (optional)
    # ------------------------------------------------------------------
    applicant_partner_id = fields.Many2one(
        'res.partner', string='Bên xin BL', required=True, tracking=True,
        default=lambda self: self.env.company.partner_id,
        help='Thường là chính company (tổng thầu).')
    beneficiary_partner_id = fields.Many2one(
        'res.partner', string='Bên thụ hưởng', required=True, tracking=True,
        help='Bên nhận BL — vd CĐT (khi tổng thầu mua BL).')
    project_id = fields.Many2one(
        're.project', string='Dự án (áp dụng)',
        help='Dự án mà BL này phục vụ. Optional — chỉ filter báo cáo.')
    # rp_contract_id: thêm bởi module rp_guarantee_bridge (depends rp_contract)

    # ------------------------------------------------------------------
    # Giá trị + Thời gian
    # ------------------------------------------------------------------
    currency_id = fields.Many2one(
        'res.currency', string='Loại tiền',
        related='credit_contract_id.currency_id',
        store=True, readonly=True)
    company_id = fields.Many2one(
        'res.company', string='Công ty',
        default=lambda self: self.env.company,
        required=True, readonly=True)
    amount = fields.Monetary(
        string='Giá trị BL', required=True, tracking=True,
        help='Số tiền NH cam kết trả nếu vi phạm. CHIẾM HẠN MỨC '
             'facility khi state=active.')
    date_request = fields.Date(
        string='Ngày đề nghị', required=True, tracking=True,
        default=fields.Date.context_today)
    date_expected_issue = fields.Date(
        string='Ngày dự kiến phát hành', tracking=True)
    date_issue = fields.Date(
        string='Ngày phát hành thực tế', tracking=True,
        help='User nhập khi kích hoạt. Mặc định = ngày kích hoạt.')
    date_expiry = fields.Date(
        string='Ngày hết hạn', required=True, tracking=True,
        help='Ngày BL hết hiệu lực. Quá ngày này mà chưa tất toán → '
             'tính phí phạt quá hạn.')

    # ------------------------------------------------------------------
    # Phí BL — auto compute từ amount × rate × days
    # ------------------------------------------------------------------
    guarantee_fee_rate = fields.Float(
        string='Tỷ lệ phí BL (%/năm)', digits=(5, 2), default=2.0,
        tracking=True,
        help='Phí BL NH thu trên giá trị BL, tính theo năm.')
    guarantee_fee_amount = fields.Monetary(
        string='Phí BL phải trả',
        compute='_compute_guarantee_fee', store=True, readonly=False,
        tracking=True,
        help='= Giá trị BL × tỷ lệ × số ngày hiệu lực / 365. User '
             'sửa được nếu NH tính khác.')
    guarantee_fee_paid = fields.Monetary(
        string='Phí BL đã trả',
        compute='_compute_paid_totals', store=True, readonly=True,
        tracking=True)
    guarantee_fee_remaining = fields.Monetary(
        string='Phí BL còn phải trả',
        compute='_compute_paid_totals', store=True)

    # ------------------------------------------------------------------
    # Ký quỹ — auto compute từ amount × rate
    # ------------------------------------------------------------------
    deposit_rate = fields.Float(
        string='Tỷ lệ ký quỹ (%)', digits=(5, 2), default=0.0,
        tracking=True)
    deposit_amount = fields.Monetary(
        string='Số tiền ký quỹ phải nộp',
        compute='_compute_deposit_amount', store=True, readonly=False,
        tracking=True)
    deposit_paid = fields.Monetary(
        string='Ký quỹ đã nộp',
        compute='_compute_paid_totals', store=True, readonly=True,
        tracking=True)
    deposit_remaining = fields.Monetary(
        string='Ký quỹ còn phải nộp',
        compute='_compute_paid_totals', store=True)

    # ------------------------------------------------------------------
    # Phạt trả chậm — tự compute từ overdue days
    # ------------------------------------------------------------------
    penalty_rate = fields.Float(
        string='Tỷ lệ phạt trả chậm (%/năm)', digits=(5, 2), default=10.0,
        help='Phạt trả chậm áp lên số phí + ký quỹ chưa trả khi quá '
             'date_expiry. Mặc định 10%/năm — chỉnh theo HĐTD.')
    penalty_days = fields.Integer(
        string='Số ngày quá hạn',
        compute='_compute_penalty', store=True)
    penalty_amount = fields.Monetary(
        string='Tiền phạt phải trả',
        compute='_compute_penalty', store=True, readonly=False,
        tracking=True,
        help='= Σ(phí + ký quỹ chưa trả) × tỷ lệ phạt × số ngày quá '
             'hạn / 365. User sửa được nếu cần.')
    penalty_paid = fields.Monetary(
        string='Phạt đã trả',
        compute='_compute_paid_totals', store=True, readonly=True,
        tracking=True)
    penalty_remaining = fields.Monetary(
        string='Phạt còn phải trả',
        compute='_compute_paid_totals', store=True)

    # ------------------------------------------------------------------
    # Tổng / progress
    # ------------------------------------------------------------------
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
             'amount. Khi True + state=active → tự tất toán.')

    # ------------------------------------------------------------------
    # Liên kết chứng thư BL chính thức (optional)
    # ------------------------------------------------------------------
    bank_guarantee_id = fields.Many2one(
        're.bank.guarantee', string='Chứng thư BL',
        copy=False,
        help='Chứng thư chi tiết NH cấp sau khi duyệt đề nghị (nếu có). '
             'Tự link / có thể chọn tay.')

    description = fields.Text(string='Diễn giải / Điều khoản')

    # ------------------------------------------------------------------
    # Payment lines
    # ------------------------------------------------------------------
    payment_ids = fields.One2many(
        're.guarantee.request.payment', 'request_id',
        string='Các đợt thanh toán')
    payment_count = fields.Integer(
        compute='_compute_payment_count')

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------
    state = fields.Selection(
        [('draft',     'Nháp'),
         ('active',    'Đã kích hoạt'),
         ('issued',    'Đã phát hành'),
         ('settled',   'Đã tất toán (legacy)'),
         ('cancelled', 'Huỷ')],
        string='Trạng thái', default='draft', required=True, tracking=True)
    date_settled = fields.Date(string='Ngày tất toán', readonly=True)
    date_issued = fields.Date(string='Ngày phát hành chứng thư',
                              readonly=True)

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends('amount', 'guarantee_fee_rate',
                 'date_issue', 'date_expiry', 'date_request',
                 'bank_guarantee_id.guarantee_fee_amount')
    def _compute_guarantee_fee(self):
        """Phí BL = giá trị × tỷ lệ × số ngày hiệu lực / 365.

        ĐÃ PHÁT HÀNH thì lấy thẳng số trên CHỨNG THƯ (backlog 727).
        Sau khi phát hành, chứng thư mới là chứng từ gốc: ngân hàng có
        thể tính phí khác dự kiến, và mọi khoản nộp đều ghi ở đó. Đề
        nghị mà vẫn giữ con số tự tính của mình thì "còn phải trả" trên
        đề nghị và trên chứng thư ra hai số khác nhau cho cùng một
        nghĩa vụ.

        start = date_issue (nếu hợp lệ, tức ≤ date_expiry),
                fallback date_request nếu date_issue trống/đảo ngược.
        end   = date_expiry.
        Robust với case user nhập date_issue > date_expiry: vẫn dùng
        date_request → date_expiry thay vì rơi về 0.
        """
        for rec in self:
            cert = rec.bank_guarantee_id
            if cert:
                rec.guarantee_fee_amount = cert.guarantee_fee_amount
                continue
            end = rec.date_expiry
            start = rec.date_issue
            if not start or (end and start > end):
                start = rec.date_request
            if start and end and end > start:
                days = (end - start).days
                rec.guarantee_fee_amount = (
                    rec.amount * (rec.guarantee_fee_rate or 0)
                    / 100.0 * days / 365.0)
            else:
                rec.guarantee_fee_amount = 0.0

    @api.depends('amount', 'deposit_rate',
                 'bank_guarantee_id.deposit_amount')
    def _compute_deposit_amount(self):
        for rec in self:
            # Đã phát hành → theo chứng thư (xem _compute_guarantee_fee).
            if rec.bank_guarantee_id:
                rec.deposit_amount = rec.bank_guarantee_id.deposit_amount
                continue
            rec.deposit_amount = (
                rec.amount * (rec.deposit_rate or 0) / 100.0)

    @api.depends('date_expiry', 'amount', 'penalty_rate', 'state',
                 'bank_guarantee_id.penalty_amount',
                 'bank_guarantee_id.penalty_days')
    def _compute_penalty(self):
        """Công thức chuẩn NH:
            penalty = giá trị BL × tỷ lệ phạt × số ngày quá hạn / 365
        Áp lên TOÀN BỘ giá trị BL (không chỉ phần phí/ký quỹ chưa trả).
        """
        today = fields.Date.context_today(self)
        for rec in self:
            # Đã phát hành → theo chứng thư (xem _compute_guarantee_fee).
            if rec.bank_guarantee_id:
                rec.penalty_days = rec.bank_guarantee_id.penalty_days
                rec.penalty_amount = rec.bank_guarantee_id.penalty_amount
                continue
            if rec.state not in ('active',) or not rec.date_expiry:
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
        Không bao gồm giá trị BL (NH chỉ thực trả khi BL bị thu).
        """
        for rec in self:
            rec.total_due = (
                rec.deposit_amount
                + rec.penalty_amount
                + rec.guarantee_fee_amount)

    @api.depends('payment_ids.amount', 'payment_ids.payment_kind',
                 'payment_ids.state',
                 'bank_guarantee_id',
                 'bank_guarantee_id.payment_ids.amount',
                 'bank_guarantee_id.payment_ids.payment_kind',
                 'bank_guarantee_id.payment_ids.state',
                 'guarantee_fee_amount', 'deposit_amount', 'penalty_amount')
    def _compute_paid_totals(self):
        """Số đã trả gộp cả hai nơi: đề nghị và chứng thư sinh ra từ nó.

        Sau khi phát hành, mọi khoản phí, ký quỹ, phạt đều ghi trên
        CHỨNG THƯ. Nếu đề nghị chỉ đếm dòng thanh toán của chính nó thì
        từ lúc phát hành trở đi nó đứng im ở con số cũ — mở đề nghị ra
        thấy "còn phải trả" nguyên vẹn trong khi tiền đã nộp xong.
        Người dùng đọc hai màn hình ra hai câu trả lời khác nhau cho
        cùng một câu hỏi.
        """
        def _by_kind(records, kind):
            return sum(
                records.filtered(
                    lambda p: p.state == 'posted'
                    and p.payment_kind == kind).mapped('amount'))

        for rec in self:
            own = rec.payment_ids
            cert_pays = (rec.bank_guarantee_id.payment_ids
                         if rec.bank_guarantee_id
                         else self.env['re.bank.guarantee.payment'])
            fee_paid = _by_kind(own, 'fee') + _by_kind(cert_pays, 'fee')
            dep_paid = (_by_kind(own, 'deposit')
                        + _by_kind(cert_pays, 'deposit'))
            pen_paid = (_by_kind(own, 'penalty')
                        + _by_kind(cert_pays, 'penalty'))
            rec.guarantee_fee_paid = fee_paid
            rec.deposit_paid = dep_paid
            rec.penalty_paid = pen_paid
            rec.guarantee_fee_remaining = max(
                0, rec.guarantee_fee_amount - fee_paid)
            rec.deposit_remaining = max(0, rec.deposit_amount - dep_paid)
            rec.penalty_remaining = max(0, rec.penalty_amount - pen_paid)
            rec.total_paid = fee_paid + dep_paid + pen_paid
            # Fully paid khi cả 3 nhóm đều đủ (có dung sai làm tròn 0.01)
            rec.is_fully_paid = (
                rec.guarantee_fee_remaining <= 0.01
                and rec.deposit_remaining <= 0.01
                and rec.penalty_remaining <= 0.01)

    @api.depends('payment_ids')
    def _compute_payment_count(self):
        for rec in self:
            rec.payment_count = len(rec.payment_ids)

    # ------------------------------------------------------------------
    # Constrains
    # ------------------------------------------------------------------
    @api.constrains('amount')
    def _check_amount(self):
        for rec in self:
            if rec.amount <= 0:
                raise ValidationError(_("Giá trị BL phải > 0."))

    def _facility_room(self):
        """Phần hạn mức thật sự còn phát hành bảo lãnh được.

        Căn theo "Khả dụng thực tế" (khả dụng theo TÀI SẢN BẢO ĐẢM)
        chứ không theo "Còn lại (theo HM)" — backlog 732. Hạn mức được
        cấp chỉ là TRẦN ngân hàng cam kết; số bảo lãnh phát hành được
        thật sự phụ thuộc bảo đảm đang có. Chặn theo trần là cho phát
        hành nhiều hơn mức tài sản đỡ nổi.

        CHẶN CỨNG, KỂ CẢ KHI KHẢ DỤNG THỰC TẾ = 0. Khách chốt như vậy,
        và chốt kèm đường đi cho trường hợp chưa phân bổ được tài sản:
        khai số vào ô "Bảo đảm khai ban đầu" trên hạn mức (xem
        re_loan_borrowing_base.borrowing_base_opening). Nhờ đó
        "chưa khai gì cả" và "đã khai nhưng hết chỗ" không còn lẫn
        nhau — cả hai đều bằng 0 nhưng cái đầu là thiếu dữ liệu, và
        người dùng có cách tự sửa.

        Vế `in fac._fields` chỉ để đỡ trường hợp CHƯA CÀI
        re_loan_borrowing_base (re_guarantee không depends vào nó).
        Đó là kiểm module có mặt hay không, KHÔNG phải kiểm dữ liệu.
        """
        self.ensure_one()
        fac = self.facility_id
        if not fac:
            return 0.0
        if 'amount_available_effective' in fac._fields:
            return fac.amount_available_effective
        return fac.amount_available

    def _msg_over_room(self, available):
        """Thông báo chặn — phải nói được ĐƯỜNG RA, không chỉ nói không.

        Khả dụng thực tế bằng 0 gần như luôn là do CHƯA KHAI bảo đảm
        chứ không phải đã dùng hết. Báo mỗi câu "vượt khả dụng" thì
        người dùng bế tắc: nhìn thấy ngân hàng cấp hạn mức đầy đủ mà
        phần mềm không cho phát hành, không biết phải làm gì.
        """
        self.ensure_one()
        fac = self.facility_id
        head = _(
            "Giá trị BL (%(b)s) vượt khả dụng thực tế của hạn mức "
            "'%(f)s' (%(a)s). Số bảo lãnh phát hành được căn theo tài "
            "sản bảo đảm đang có, không phải theo trần hạn mức ngân "
            "hàng cấp.",
            b='{:,.0f}'.format(self.amount or 0),
            f=fac.name or '',
            a='{:,.0f}'.format(available or 0))
        if (available or 0) <= 0.01:
            head += _(
                "\n\nHạn mức này chưa khai bảo đảm nào nên khả dụng "
                "thực tế đang bằng 0. Mở hạn mức '%(f)s' rồi làm MỘT "
                "trong hai cách:\n"
                "• Khai số vào ô \"Bảo đảm khai ban đầu\" — dùng khi "
                "ngân hàng cấp trên cả rổ tài sản mà hồ sơ không tách "
                "được từng tài sản;\n"
                "• Hoặc phân bổ tài sản bảo đảm cho mục đích này ở tab "
                "Phân bổ TSBĐ.",
                f=fac.name or '')
        return head

    def _own_room_contribution(self):
        """Phần hạn mức mà CHÍNH đề nghị này đang chiếm.

        Phải là ĐẢO NGƯỢC ĐÚNG của phần cộng thêm trong
        re.loan.facility._compute_amount_used (module re_guarantee),
        không được lệch một trạng thái nào:

          - 'active'  → đề nghị đang chiếm `amount` (backlog 732)
          - 'issued'  → đề nghị thôi chiếm, CHỨNG THƯ chiếm thay nên
                        lấy số của chứng thư (có thể khác số đề nghị
                        nếu ngân hàng phát hành số khác)
          - còn lại   → không chiếm gì

        Dùng để cộng ngược vào "khả dụng" khi kiểm chính bản ghi này:
        thiếu thì đề nghị chiếm trọn hạn mức sẽ tự chặn chính mình.
        """
        self.ensure_one()
        if self.state == 'active':
            return self.amount or 0.0
        if self.state == 'issued':
            cert = self.bank_guarantee_id
            if cert and cert.state in ('issued', 'extended', 'forfeited'):
                return cert.amount or 0.0
        return 0.0

    @api.constrains('amount', 'facility_id', 'state')
    def _check_amount_within_facility(self):
        """Chặn nhập giá trị BL > khả dụng thực tế của hạn mức.

        Draft: chưa chiếm gì, so thẳng với khả dụng.
        Active / issued: đã nằm trong `amount_used` rồi nên cộng ngược
        phần đang chiếm, bằng không phép kiểm sẽ so bản ghi với phần
        trống ĐÃ TRỪ chính nó.
        """
        for rec in self:
            if not rec.facility_id or rec.amount <= 0:
                continue
            if rec.state in ('settled', 'cancelled'):
                continue
            available = rec._facility_room() + rec._own_room_contribution()
            if available + 0.01 < rec.amount:
                raise ValidationError(
                    rec._msg_over_room(available))

    @api.onchange('amount', 'facility_id')
    def _onchange_amount_warning(self):
        """Cảnh báo sớm trên UI khi user nhập amount > available."""
        if (self.facility_id and self.amount
                and self.state == 'draft'
                and self.amount > self._facility_room() + 0.01):
            return {
                'warning': {
                    'title': _("Vượt hạn mức bảo lãnh"),
                    'message': _(
                        "Giá trị BL %(b)s lớn hơn khả dụng thực tế "
                        "%(a)s của hạn mức '%(f)s'. Sẽ không lưu "
                        "được nếu không giảm xuống.",
                        b=self.amount, a=self._facility_room(),
                        f=self.facility_id.name),
                },
            }

    @api.constrains('date_expiry', 'date_request', 'date_issue')
    def _check_dates(self):
        """Ba mốc phải đi đúng thứ tự đời thực: đề nghị → phát hành →
        hết hạn.

        Gõ ngược thì phí bảo lãnh tính theo số ngày âm, và chứng thư
        sinh ra từ đề nghị mang luôn ngày sai sang.
        """
        for rec in self:
            if rec.date_expiry and rec.date_request and (
                    rec.date_expiry <= rec.date_request):
                raise ValidationError(_(
                    "Ngày hết hạn phải sau ngày đề nghị."))
            if (rec.date_issue and rec.date_request
                    and rec.date_issue < rec.date_request):
                raise ValidationError(_(
                    'Ngày phát hành thực tế (%(i)s) không được sớm hơn '
                    'Ngày đề nghị (%(r)s).',
                    i=rec.date_issue, r=rec.date_request))
            if (rec.date_expiry and rec.date_issue
                    and rec.date_expiry < rec.date_issue):
                raise ValidationError(_(
                    'Ngày hết hạn (%(e)s) không được sớm hơn Ngày phát '
                    'hành thực tế (%(i)s).',
                    e=rec.date_expiry, i=rec.date_issue))

    # ------------------------------------------------------------------
    # Create — auto sequence
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _('/'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    're.guarantee.request') or _('/')
        return super().create(vals_list)

    # ------------------------------------------------------------------
    # State machine
    # ------------------------------------------------------------------
    def action_activate(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_(
                    "Chỉ đề nghị ở trạng thái Nháp mới kích hoạt được."))
            if not rec.facility_id:
                raise UserError(_(
                    "Cần chọn hạn mức bảo lãnh trước khi kích hoạt."))
            # Kích hoạt LÀ lúc chiếm hạn mức (backlog 732), nên phép
            # kiểm ở đây phải căn theo KHẢ DỤNG THỰC TẾ — cùng thước
            # với lúc phát hành. Trước đây bước này đo bằng "Còn lại
            # theo trần hạn mức" còn bước phát hành đo bằng khả dụng
            # thực tế: kích hoạt lọt, tới lúc phát hành mới chặn.
            available = rec._facility_room()
            if available + 0.01 < rec.amount:
                raise UserError(rec._msg_over_room(available))
            rec.state = 'active'
            if not rec.date_issue:
                rec.date_issue = fields.Date.context_today(rec)
            rec.message_post(body=_(
                "Kích hoạt đề nghị BL %(a)s trên hạn mức %(f)s — hạn "
                "mức bị chiếm TỪ BÂY GIỜ, không chờ tới lúc phát hành "
                "chứng thư.",
                a='{:,.0f}'.format(rec.amount or 0.0),
                f=rec.facility_id.name))

    def action_issue(self):
        """Phát hành chứng thư BL từ đề nghị này.

        Workflow: active → issued. Tạo re.bank.guarantee mới, copy
        toàn bộ thông tin từ đề nghị, link 2 chiều
        (request.bank_guarantee_id ↔ certificate.guarantee_request_id).

        Sau phát hành, đề nghị chuyển 'issued' (chỉ đọc); tracking
        thanh toán + tất toán chuyển sang chứng thư.
        """
        self.ensure_one()
        if self.state != 'active':
            raise UserError(_(
                "Chỉ phát hành được khi đề nghị đang Đã kích hoạt."))
        if self.bank_guarantee_id:
            raise UserError(_(
                "Đề nghị này đã có chứng thư BL — không phát hành mới."))
        # Vẫn kiểm lại lúc phát hành: giữa kích hoạt và phát hành có
        # thể hạn mức đã hụt đi (tài sản bảo đảm được định giá lại,
        # hoặc phần bảo đảm khai ban đầu bị sửa xuống).
        #
        # PHẢI cộng ngược phần đề nghị này đang chiếm: từ lúc kích
        # hoạt nó đã nằm trong `amount_used`, nên `_facility_room()`
        # đã trừ chính nó rồi. Không cộng lại thì đề nghị chiếm trọn
        # hạn mức tự chặn chính mình — đúng lỗi đếm hai lần đã gặp ở
        # khế ước (backlog 716).
        if self.facility_id:
            available = self._facility_room() + self._own_room_contribution()
            if available + 0.01 < self.amount:
                raise UserError(self._msg_over_room(available))
        today = fields.Date.context_today(self)
        cert_vals = self._prepare_bank_guarantee_vals()
        cert = self.env['re.bank.guarantee'].create(cert_vals)
        # Copy payment lines từ request → certificate (nếu user đã trả
        # ký quỹ trước khi phát hành)
        for pay in self.payment_ids.filtered(lambda p: p.state == 'posted'):
            self.env['re.bank.guarantee.payment'].create({
                'guarantee_id': cert.id,
                'date': pay.date,
                'payment_kind': pay.payment_kind,
                'amount': pay.amount,
                'reference': pay.reference,
                'name': pay.name,
                'state': 'posted',
            })
        self.write({
            'bank_guarantee_id': cert.id,
            'state': 'issued',
            'date_issued': today,
        })
        # Facility: request 'issued' không còn chiếm; certificate 'issued'
        # giờ chiếm thay → net consumption không đổi nhưng recompute để
        # đảm bảo các cache UI cập nhật.
        if self.facility_id:
            self.facility_id._compute_amount_used()
            self.facility_id._compute_amount_available()
        self.message_post(body=_(
            "Phát hành chứng thư BL %(c)s từ đề nghị này.", c=cert.name))
        return {
            'type': 'ir.actions.act_window',
            'name': _("Chứng thư BL"),
            'res_model': 're.bank.guarantee',
            'res_id': cert.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _prepare_bank_guarantee_vals(self):
        """Hook copy fields request → certificate. Bridge modules có
        thể override để bổ sung field (vd rp_contract_id).
        """
        self.ensure_one()
        return {
            'guarantee_type': self.guarantee_type,
            'issuing_bank_partner_id': self.issuing_bank_partner_id.id,
            'applicant_partner_id': self.applicant_partner_id.id,
            'beneficiary_partner_id': self.beneficiary_partner_id.id,
            'facility_id': self.facility_id.id,
            'amount': self.amount,
            'currency_id': self.currency_id.id,
            'date_issue': (self.date_issue
                           or fields.Date.context_today(self)),
            'date_expiry': self.date_expiry,
            'guarantee_fee_rate': self.guarantee_fee_rate,
            'guarantee_fee_amount': self.guarantee_fee_amount,
            'deposit_rate': self.deposit_rate,
            'deposit_amount': self.deposit_amount,
            'penalty_rate': self.penalty_rate,
            'description': self.description or '',
            'state': 'issued',
            'guarantee_request_id': self.id,
        }

    def action_settle(self):
        """LEGACY tất toán đề nghị BL — vẫn giữ để xử lý records cũ.

        Workflow mới: tất toán nằm trên chứng thư BL (re.bank.guarantee).
        """
        for rec in self:
            if rec.state != 'active':
                raise UserError(_(
                    "Chỉ BL Đã kích hoạt mới tất toán được (legacy)."))
            rec.state = 'settled'
            rec.date_settled = fields.Date.context_today(rec)
            rec.facility_id._compute_amount_used()
            rec.facility_id._compute_amount_available()
            rec.message_post(body=_(
                "(Legacy) Tất toán đề nghị — khôi phục hạn mức."))

    def action_cancel(self):
        """Huỷ đề nghị thì huỷ luôn chứng thư sinh ra từ nó.

        Chứng thư là hệ quả của đề nghị chứ không phải hồ sơ độc lập.
        Để đề nghị "Huỷ" mà chứng thư vẫn "Đã phát hành" là hai văn bản
        nói ngược nhau — và chứng thư đó vẫn âm thầm chiếm hạn mức.
        """
        for rec in self:
            if rec.state not in ('draft', 'active', 'issued'):
                raise UserError(_(
                    "Chỉ huỷ được BL ở Nháp, Đã kích hoạt hoặc Đã "
                    "phát hành."))
            cert = rec.bank_guarantee_id
            if cert and cert.state not in ('draft', 'issued', 'extended'):
                raise UserError(_(
                    "Chứng thư %(c)s đang ở trạng thái '%(s)s' — không "
                    "huỷ đề nghị được. Xử lý chứng thư trước.",
                    c=cert.name,
                    s=dict(cert._fields['state'].selection).get(
                        cert.state)))
            if rec.state == 'active' and rec.total_paid > 0:
                raise UserError(_(
                    "Đã phát sinh thanh toán trên BL này — không huỷ "
                    "được. Tất toán thay vì huỷ."))
            cert = rec.bank_guarantee_id
            if cert and cert.state != 'released':
                cert.write({
                    'state': 'released',
                    'date_released': fields.Date.context_today(rec),
                    'release_reason': _('Huỷ theo đề nghị %s') % rec.name,
                })
                cert.message_post(body=_(
                    'Chứng thư huỷ theo đề nghị phát hành %s.', rec.name))
            rec.state = 'cancelled'
            if rec.facility_id:
                rec.facility_id._compute_amount_used()
                rec.facility_id._compute_amount_available()

    def action_reset_draft(self):
        for rec in self:
            if rec.state != 'cancelled':
                raise UserError(_(
                    "Chỉ BL Đã huỷ mới đưa về Nháp được."))
            rec.state = 'draft'

    def _check_auto_settle(self):
        """Auto-settle DEPRECATED — workflow mới: chuyển sang phát hành
        chứng thư BL rồi auto-settle trên chứng thư. No-op trên request."""
        return

    def action_view_payments(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Thanh toán — %s") % self.name,
            'res_model': 're.guarantee.request.payment',
            'view_mode': 'list,form',
            'domain': [('request_id', '=', self.id)],
            'context': {
                'default_request_id': self.id,
                'default_currency_id': self.currency_id.id,
            },
        }


class ReGuaranteeRequestPayment(models.Model):
    _name = 're.guarantee.request.payment'
    _description = 'Đợt thanh toán Đề nghị BL'
    _order = 'date desc, id desc'

    request_id = fields.Many2one(
        're.guarantee.request', string='Đề nghị BL',
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
        string='Trạng thái', default='posted', required=True,
        help='Posted ngay khi tạo — quan điểm: user chỉ nhập khi đã '
             'có chứng từ thật.')

    currency_id = fields.Many2one(
        related='request_id.currency_id', store=True, readonly=True)
    company_id = fields.Many2one(
        related='request_id.company_id', store=True, readonly=True)

    @api.constrains('amount')
    def _check_amount(self):
        for rec in self:
            if rec.amount <= 0:
                raise ValidationError(_("Số tiền thanh toán phải > 0."))

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        recs.request_id._check_auto_settle()
        return recs

    def write(self, vals):
        res = super().write(vals)
        self.request_id._check_auto_settle()
        return res

    def unlink(self):
        requests = self.request_id
        res = super().unlink()
        # Sau khi xoá payment, có thể chưa fully paid nữa — không
        # auto-revert state (settled → active). Manager xử lý tay nếu cần.
        return res
