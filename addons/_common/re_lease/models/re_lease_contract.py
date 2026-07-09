# -*- coding: utf-8 -*-
"""HĐ thuê tài sản — ma trận 2×2: direction × lease_type.

Đi thuê (in) / Cho thuê lại (out) × Hoạt động (operating) / Tài chính
(finance). Lịch thuê tài chính tách gốc+lãi (pattern KW); kế toán tích
hợp qua hóa đơn chuẩn account.move.
"""
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class ReLeaseContract(models.Model):
    _name = 're.lease.contract'
    _description = 'Hợp đồng thuê tài sản'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_start desc, id desc'

    name = fields.Char(
        string='Số HĐ thuê', required=True, copy=False, tracking=True)
    direction = fields.Selection(
        [('in', 'Đi thuê'), ('out', 'Cho thuê lại')],
        string='Chiều', required=True, default='in', tracking=True)
    lease_type = fields.Selection(
        [('operating', 'Hoạt động'), ('finance', 'Tài chính')],
        string='Loại thuê', required=True, default='operating',
        tracking=True,
        help='Tài chính: chuyển giao phần lớn rủi ro/lợi ích (thuê mua, '
             'quyền mua lại giá ưu đãi...) — lịch tách gốc+lãi. '
             'Hoạt động: thuê thường, tiền thuê đều theo kỳ.')
    partner_id = fields.Many2one(
        'res.partner', string='Đối tác', required=True, tracking=True,
        help='Đi thuê: bên cho thuê (công ty leasing / chủ thiết bị). '
             'Cho thuê lại: bên thuê (nhà thầu phụ / công ty nội bộ).')
    project_id = fields.Many2one(
        're.project', string='Dự án', ondelete='set null', index=True,
        help='Dự án thiết bị phục vụ (tham khảo, không bắt buộc).')

    # Back-to-back: cho thuê lại từ HĐ đi thuê gốc
    parent_lease_id = fields.Many2one(
        're.lease.contract', string='HĐ đi thuê gốc',
        domain="[('direction', '=', 'in'), ('id', '!=', id)]",
        index=True, tracking=True,
        help='Khi CHO THUÊ LẠI thiết bị đang đi thuê — link về HĐ đi '
             'thuê gốc để theo dõi chênh lệch (back-to-back).')
    child_lease_ids = fields.One2many(
        're.lease.contract', 'parent_lease_id',
        string='HĐ cho thuê lại')
    child_lease_count = fields.Integer(compute='_compute_backtoback')

    date_sign = fields.Date(string='Ngày ký')
    date_start = fields.Date(
        string='Ngày bắt đầu', required=True, tracking=True)
    n_periods = fields.Integer(
        string='Số kỳ', default=12, tracking=True)
    period_months = fields.Selection(
        [('1', 'Hằng tháng'), ('3', 'Hằng quý'),
         ('6', '6 tháng'), ('12', 'Hằng năm')],
        string='Chu kỳ', default='1', required=True)
    payment_day = fields.Integer(
        string='Ngày thanh toán',
        help='Ngày trong tháng phải thanh toán CHẬM NHẤT (vd 10 = chậm '
             'nhất ngày 10). Bỏ trống = đúng ngày đến hạn theo chu kỳ. '
             'Nếu tháng không có ngày này thì lấy ngày cuối tháng.')
    date_end = fields.Date(
        string='Ngày kết thúc', compute='_compute_date_end', store=True)
    deposit = fields.Monetary(
        string='Ký cược / đặt cọc', tracking=True)

    # --- Tài chính ---
    amount_financed = fields.Monetary(
        string='Giá trị tài trợ', tracking=True,
        help='Nợ gốc thuê tài chính ban đầu (giá trị tài sản được tài '
             'trợ, trước thuế).')
    interest_rate = fields.Float(
        string='Lãi suất (%/năm)', digits=(6, 2), tracking=True,
        help='Lãi suất ngầm định trong HĐ thuê tài chính.')
    principal_plan = fields.Selection(
        [('equal_principal', 'Gốc đều'),
         ('annuity', 'Niên kim (tổng kỳ đều)')],
        string='Cách trả gốc', default='equal_principal')
    buyout_price = fields.Monetary(
        string='Giá mua lại cuối kỳ',
        help='Giá chuyển quyền sở hữu khi hết hạn (thường tượng trưng).')

    # --- Hoạt động ---
    rent_per_period = fields.Monetary(
        string='Tiền thuê / kỳ (trước thuế)', tracking=True,
        compute='_compute_rent_per_period', store=True, readonly=False,
        help='Tự tổng "Số tiền thuê" của các tài sản khi đã khai đơn giá '
             'theo tài sản; nếu chưa khai thì nhập tay.')

    @api.depends('asset_ids.rent_subtotal')
    def _compute_rent_per_period(self):
        for rec in self:
            subtotal = sum(rec.asset_ids.mapped('rent_subtotal'))
            # Có khai đơn giá theo tài sản → tổng lên; chưa khai → giữ
            # nguyên giá trị nhập tay (không ghi đè về 0).
            rec.rent_per_period = subtotal if subtotal else rec.rent_per_period

    tax_id = fields.Many2one(
        'account.tax', string='Thuế VAT',
        help='Thuế áp lên dòng tiền thuê / lãi trên hóa đơn (nếu có).')

    state = fields.Selection(
        [('draft', 'Nháp'),
         ('active', 'Hiệu lực'),
         ('ended', 'Kết thúc'),
         ('terminated', 'Chấm dứt sớm')],
        string='Trạng thái', default='draft', required=True, tracking=True)

    asset_ids = fields.One2many(
        're.lease.asset', 'contract_id', string='Tài sản thuê')
    payment_line_ids = fields.One2many(
        're.lease.payment.line', 'contract_id', string='Lịch thanh toán')
    annex_ids = fields.One2many(
        're.lease.annex', 'contract_id', string='Phụ lục')
    annex_count = fields.Integer(
        string='Số phụ lục', compute='_compute_annex_count')

    # --- Chấm dứt sớm ---
    termination_date = fields.Date(string='Ngày chấm dứt', readonly=True)
    termination_reason = fields.Text(string='Lý do chấm dứt', readonly=True)
    penalty_amount = fields.Monetary(
        string='Phạt / bồi thường', readonly=True)

    # --- Thanh lý ---
    liquidated = fields.Boolean(string='Đã thanh lý', readonly=True,
                                copy=False)
    liquidation_date = fields.Date(string='Ngày thanh lý', readonly=True)
    repair_deduction = fields.Monetary(
        string='Khấu trừ sửa chữa / hư hỏng', readonly=True)
    other_deduction = fields.Monetary(
        string='Khấu trừ khác', readonly=True)
    deposit_refund = fields.Monetary(
        string='Hoàn ký cược', readonly=True,
        help='Ký cược − khấu trừ (không âm).')
    final_settlement = fields.Monetary(
        string='Quyết toán cuối (thu/trả)', readonly=True)
    asset_return_ok = fields.Boolean(
        string='Đã nhận/trả lại tài sản', readonly=True)

    # --- Kế toán (tab Kế toán — hiện theo direction × type) ---
    journal_id = fields.Many2one(
        'account.journal', string='Sổ nhật ký (bút toán)',
        domain="[('type', '=', 'general')]",
        help='Dùng cho bút toán ghi nhận tài sản thuê TC (Nợ TS thuê '
             'TC / Có Nợ gốc thuê TC).')
    account_asset_id = fields.Many2one(
        'account.account', string='TK tài sản thuê TC (212...)',
        help='Đi thuê tài chính: TK ghi nhận tài sản thuê tài chính.')
    account_liability_id = fields.Many2one(
        'account.account', string='TK nợ gốc thuê TC (341x...)',
        help='Đi thuê tài chính: TK nợ gốc; dòng GỐC trên hóa đơn NCC '
             'từng kỳ ghi vào TK này → giảm nợ.')
    account_interest_id = fields.Many2one(
        'account.account', string='TK lãi thuê (635 / 515)',
        help='Đi thuê: chi phí lãi (635). Cho thuê lại: doanh thu tài '
             'chính (515).')
    account_rent_id = fields.Many2one(
        'account.account', string='TK tiền thuê (627.../511x)',
        help='Đi thuê hoạt động: TK chi phí thuê. Cho thuê lại hoạt '
             'động: TK doanh thu cho thuê. Bỏ trống → TK mặc định của '
             'sổ nhật ký hóa đơn.')
    account_receivable_finance_id = fields.Many2one(
        'account.account', string='TK phải thu thuê TC',
        help='Cho thuê lại tài chính: dòng GỐC trên hóa đơn bán ghi '
             'vào TK này → giảm phải thu dài hạn.')
    recognition_move_id = fields.Many2one(
        'account.move', string='Bút toán ghi nhận TS thuê TC',
        readonly=True, copy=False)
    derecognition_move_id = fields.Many2one(
        'account.move', string='Bút toán chuyển giao TS (cho thuê lại TC)',
        readonly=True, copy=False)

    # --- Khấu hao tài sản thuê TC (đi thuê tài chính) — Phase 2 ---
    account_depreciation_expense_id = fields.Many2one(
        'account.account', string='TK chi phí khấu hao (627/641/642)',
        help='Nợ chi phí khấu hao mỗi kỳ.')
    account_depreciation_id = fields.Many2one(
        'account.account', string='TK hao mòn lũy kế (2142)',
        help='Có hao mòn TSCĐ thuê tài chính mỗi kỳ.')
    depreciation_months = fields.Integer(
        string='Số tháng khấu hao',
        help='Đường thẳng theo tháng. 0 = lấy bằng thời hạn thuê '
             '(số kỳ × chu kỳ).')
    depreciation_line_ids = fields.One2many(
        're.lease.depreciation.line', 'contract_id',
        string='Lịch khấu hao')
    depreciated_total = fields.Monetary(
        string='Đã khấu hao', compute='_compute_depreciation_totals')
    depreciation_remaining = fields.Monetary(
        string='Giá trị còn lại', compute='_compute_depreciation_totals')

    # --- Tổng hợp ---
    amount_asset_total = fields.Monetary(
        string='Tổng giá trị tài sản', compute='_compute_totals')
    outstanding_principal = fields.Monetary(
        string='Dư nợ gốc còn lại', compute='_compute_totals',
        help='Thuê tài chính: gốc chưa nằm trên hóa đơn đã vào sổ.')
    invoiced_to_date = fields.Monetary(
        string='Đã lên hóa đơn (trước thuế)', compute='_compute_totals')
    paid_to_date = fields.Monetary(
        string='Đã thanh toán (kỳ đã trả)', compute='_compute_totals')
    next_due_date = fields.Date(
        string='Kỳ đến hạn kế tiếp', compute='_compute_totals')
    # Back-to-back margin (trên HĐ đi thuê gốc)
    sublease_revenue = fields.Monetary(
        string='Doanh thu cho thuê lại', compute='_compute_backtoback',
        help='Σ hóa đơn bán đã vào sổ của các HĐ cho thuê lại link về '
             'HĐ này (trước thuế).')
    own_lease_cost = fields.Monetary(
        string='Chi phí đi thuê', compute='_compute_backtoback',
        help='Σ hóa đơn NCC đã vào sổ của chính HĐ này (trước thuế).')
    sublease_margin = fields.Monetary(
        string='Chênh lệch cho thuê lại', compute='_compute_backtoback')

    currency_id = fields.Many2one(
        'res.currency', required=True,
        default=lambda self: self.env.company.currency_id)
    company_id = fields.Many2one(
        'res.company', required=True,
        default=lambda self: self.env.company)
    note = fields.Text(string='Ghi chú')

    _sql_constraints = [
        ('name_company_unique', 'unique(name, company_id)',
         'Số HĐ thuê đã tồn tại.'),
    ]

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends('date_start', 'n_periods', 'period_months')
    def _compute_date_end(self):
        for rec in self:
            if rec.date_start and rec.n_periods:
                rec.date_end = rec.date_start + relativedelta(
                    months=int(rec.period_months) * rec.n_periods)
            else:
                rec.date_end = False

    @api.depends('asset_ids.value', 'payment_line_ids.principal_amount',
                 'payment_line_ids.state', 'payment_line_ids.amount_total',
                 'payment_line_ids.date_due', 'amount_financed',
                 'lease_type')
    def _compute_totals(self):
        today = fields.Date.context_today(self)
        for rec in self:
            rec.amount_asset_total = sum(rec.asset_ids.mapped('value'))
            lines = rec.payment_line_ids
            billed = lines.filtered(lambda l: l.state != 'draft')
            rec.invoiced_to_date = sum(billed.mapped('amount_total'))
            rec.paid_to_date = sum(
                lines.filtered(lambda l: l.state == 'paid')
                .mapped('amount_total'))
            if rec.lease_type == 'finance':
                rec.outstanding_principal = rec.amount_financed - sum(
                    billed.mapped('principal_amount'))
            else:
                rec.outstanding_principal = 0.0
            upcoming = lines.filtered(
                lambda l: l.state != 'paid' and l.date_due
                and l.date_due >= today).sorted('date_due')
            rec.next_due_date = upcoming[:1].date_due if upcoming else False

    @api.depends('child_lease_ids',
                 'child_lease_ids.payment_line_ids.state',
                 'child_lease_ids.payment_line_ids.amount_total',
                 'payment_line_ids.state', 'payment_line_ids.amount_total')
    def _compute_backtoback(self):
        for rec in self:
            rec.child_lease_count = len(rec.child_lease_ids)
            child_lines = rec.child_lease_ids.mapped('payment_line_ids')
            rec.sublease_revenue = sum(
                child_lines.filtered(lambda l: l.state != 'draft')
                .mapped('amount_total'))
            own_lines = rec.payment_line_ids.filtered(
                lambda l: l.state != 'draft')
            rec.own_lease_cost = sum(own_lines.mapped('amount_total'))
            rec.sublease_margin = rec.sublease_revenue - rec.own_lease_cost

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------
    @api.constrains('lease_type', 'amount_financed', 'interest_rate',
                    'rent_per_period', 'n_periods')
    def _check_amounts(self):
        for rec in self:
            if rec.n_periods <= 0:
                raise ValidationError(_('Số kỳ phải lớn hơn 0.'))
            if rec.lease_type == 'finance':
                if rec.amount_financed <= 0:
                    raise ValidationError(_(
                        'Thuê tài chính: Giá trị tài trợ phải lớn hơn 0.'))
                if rec.interest_rate < 0:
                    raise ValidationError(_('Lãi suất không được âm.'))
            else:
                if rec.rent_per_period <= 0:
                    raise ValidationError(_(
                        'Thuê hoạt động: Tiền thuê / kỳ phải lớn hơn 0.'))

    @api.constrains('payment_day')
    def _check_payment_day(self):
        for rec in self:
            if rec.payment_day and not (1 <= rec.payment_day <= 31):
                raise ValidationError(_(
                    'Ngày thanh toán phải từ 1 đến 31.'))

    @api.constrains('parent_lease_id', 'direction')
    def _check_parent(self):
        for rec in self:
            if rec.parent_lease_id and rec.direction != 'out':
                raise ValidationError(_(
                    'Chỉ HĐ CHO THUÊ LẠI mới link HĐ đi thuê gốc.'))
            if rec.parent_lease_id and \
                    rec.parent_lease_id.direction != 'in':
                raise ValidationError(_(
                    'HĐ gốc phải là HĐ ĐI THUÊ.'))

    # ------------------------------------------------------------------
    # Lịch thanh toán
    # ------------------------------------------------------------------
    def _compute_annex_count(self):
        for rec in self:
            rec.annex_count = len(rec.annex_ids)

    def _reschedule_future_operating_lines(self):
        """Tạo lại các kỳ CHƯA lên hóa đơn theo n_periods / rent / chu kỳ
        hiện tại — GIỮ NGUYÊN kỳ đã lên hóa đơn. Dùng khi áp dụng phụ lục
        (điều chỉnh giá / gia hạn / rút ngắn / chu kỳ). Chỉ thuê hoạt động;
        thuê tài chính cần soạn lại lịch thủ công (biên độ khấu hao)."""
        self.ensure_one()
        if self.lease_type != 'operating':
            return
        billed = self.payment_line_ids.filtered(lambda l: l.state != 'draft')
        # Bắt đầu kỳ mới SAU kỳ đã lên hóa đơn cuối cùng (an toàn kể cả
        # khi bill không liền mạch); không tụt dưới số kỳ đã bill.
        start = max(billed.mapped('sequence'), default=0) + 1
        if self.n_periods < len(billed):
            raise UserError(_(
                "Không thể còn %(x)s kỳ — đã có %(b)s kỳ lên hóa đơn.",
                x=self.n_periods, b=len(billed)))
        self.payment_line_ids.filtered(
            lambda l: l.state == 'draft').unlink()
        vals = [{
            'contract_id': self.id,
            'sequence': i,
            'date_due': self._period_date(i),
            'rent_amount': self._period_rent(i),
        } for i in range(start, self.n_periods + 1)]
        if vals:
            self.env['re.lease.payment.line'].create(vals)

    def action_open_annexes(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Phụ lục — %s', self.name),
            'res_model': 're.lease.annex',
            'view_mode': 'list,form',
            'domain': [('contract_id', '=', self.id)],
            'context': {'default_contract_id': self.id},
        }

    def action_generate_schedule(self):
        for rec in self:
            if rec.state not in ('draft', 'active'):
                raise UserError(_(
                    'Chỉ tạo lịch cho HĐ Nháp / Hiệu lực.'))
            locked = rec.payment_line_ids.filtered(
                lambda l: l.state != 'draft')
            if locked:
                raise UserError(_(
                    'HĐ đã có %(n)s kỳ lên hóa đơn — không tạo lại lịch '
                    'được (huỷ hóa đơn trước).', n=len(locked)))
            rec.payment_line_ids.unlink()
            vals_list = (rec._build_finance_lines()
                         if rec.lease_type == 'finance'
                         else rec._build_operating_lines())
            self.env['re.lease.payment.line'].create(vals_list)
            rec.message_post(body=_(
                'Đã tạo lịch thanh toán %(n)s kỳ.', n=rec.n_periods))
        return True

    def _period_date(self, i):
        """Ngày đến hạn kỳ i (1-based) = date_start + i chu kỳ; nếu khai
        'Ngày thanh toán' thì đặt về ngày đó trong tháng (cap ngày cuối
        tháng)."""
        import calendar
        due = self.date_start + relativedelta(
            months=int(self.period_months) * i)
        if self.payment_day:
            last = calendar.monthrange(due.year, due.month)[1]
            due = due.replace(day=min(max(1, self.payment_day), last))
        return due

    def _period_ref(self, i):
        """Ngày ĐẦU kỳ i — dùng xác định tài sản nào đang thuê trong kỳ."""
        return self.date_start + relativedelta(
            months=int(self.period_months) * (i - 1))

    def _period_rent(self, i):
        """Tiền thuê kỳ i = Σ 'Số tiền thuê' của các tài sản ĐANG THUÊ
        trong kỳ (theo Ngày bắt đầu/kết thúc từng tài sản). Nếu chưa khai
        đơn giá theo tài sản → dùng Tiền thuê/kỳ của HĐ (tương thích cũ)."""
        priced = self.asset_ids.filtered('rent_subtotal')
        if not priced:
            return self.rent_per_period
        ref = self._period_ref(i)
        total = 0.0
        for a in priced:
            a_start = a.date_start or self.date_start
            a_end = a.date_end or self.date_end
            if a_start <= ref and (not a_end or ref <= a_end):
                total += a.rent_subtotal
        return total

    def _build_operating_lines(self):
        self.ensure_one()
        return [{
            'contract_id': self.id,
            'sequence': i,
            'date_due': self._period_date(i),
            'rent_amount': self._period_rent(i),
        } for i in range(1, self.n_periods + 1)]

    def _build_finance_lines(self):
        self.ensure_one()
        n = self.n_periods
        principal = self.amount_financed
        r = (self.interest_rate / 100.0) * int(self.period_months) / 12.0
        vals, balance = [], principal
        if self.principal_plan == 'annuity' and r > 0:
            payment = principal * r / (1 - (1 + r) ** -n)
        else:
            payment = None  # gốc đều
        for i in range(1, n + 1):
            interest = balance * r
            if payment is not None:
                pr = payment - interest
            else:
                pr = principal / n
            if i == n:
                pr = balance  # kỳ cuối vét sạch (khử làm tròn)
            balance -= pr
            vals.append({
                'contract_id': self.id,
                'sequence': i,
                'date_due': self._period_date(i),
                'principal_amount': pr,
                'interest_amount': interest,
                'balance_after': balance,
            })
        return vals

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------
    def action_activate(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Chỉ kích hoạt HĐ Nháp.'))
            if not rec.payment_line_ids:
                raise UserError(_(
                    'Tạo lịch thanh toán trước khi kích hoạt.'))
            rec.state = 'active'

    def action_end(self):
        self.filtered(lambda r: r.state == 'active').write(
            {'state': 'ended'})

    def action_terminate(self):
        """Mở wizard chấm dứt sớm (khai lý do / ngày / phạt)."""
        self.ensure_one()
        if self.state not in ('draft', 'active'):
            raise UserError(_('HĐ đã kết thúc.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Chấm dứt sớm HĐ thuê'),
            'res_model': 're.lease.terminate.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_contract_id': self.id},
        }

    def _apply_termination(self, date, reason, penalty):
        self.ensure_one()
        self.write({
            'state': 'terminated',
            'termination_date': date,
            'termination_reason': reason,
            'penalty_amount': penalty or 0.0,
        })
        self.message_post(body=_(
            'Chấm dứt sớm ngày %(d)s. Phạt/bồi thường: %(p)s. Lý do: '
            '%(r)s. Các kỳ chưa lên hóa đơn sẽ không thu/trả nữa.',
            d=date, p='{:,.0f}'.format(penalty or 0.0),
            r=reason or '—'))

    def action_open_liquidation(self):
        """Mở wizard thanh lý (quyết toán + hoàn cọc + trả tài sản)."""
        self.ensure_one()
        if self.state == 'draft':
            raise UserError(_('HĐ Nháp chưa cần thanh lý.'))
        if self.liquidated:
            raise UserError(_('HĐ đã thanh lý.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Thanh lý HĐ thuê'),
            'res_model': 're.lease.liquidation.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_contract_id': self.id},
        }

    def _apply_liquidation(self, vals):
        self.ensure_one()
        self.write(dict(vals, liquidated=True))
        self.message_post(body=_(
            'Thanh lý ngày %(d)s. Hoàn ký cược: %(r)s. Quyết toán cuối: '
            '%(f)s.',
            d=vals.get('liquidation_date'),
            r='{:,.0f}'.format(vals.get('deposit_refund') or 0.0),
            f='{:,.0f}'.format(vals.get('final_settlement') or 0.0)))

    # ------------------------------------------------------------------
    # Kế toán
    # ------------------------------------------------------------------
    def action_post_recognition(self):
        """Đi thuê TÀI CHÍNH: Nợ TS thuê TC / Có Nợ gốc thuê TC."""
        for rec in self:
            if rec.direction != 'in' or rec.lease_type != 'finance':
                raise UserError(_(
                    'Bút toán ghi nhận chỉ áp dụng HĐ ĐI THUÊ TÀI CHÍNH.'))
            if rec.recognition_move_id:
                raise UserError(_(
                    'Đã có bút toán ghi nhận (%(m)s).',
                    m=rec.recognition_move_id.name))
            if not (rec.journal_id and rec.account_asset_id
                    and rec.account_liability_id):
                raise UserError(_(
                    'Khai đủ Sổ nhật ký + TK tài sản thuê TC + TK nợ '
                    'gốc thuê TC (tab Kế toán) trước.'))
            move = self.env['account.move'].create({
                'move_type': 'entry',
                'journal_id': rec.journal_id.id,
                'date': rec.date_start,
                'ref': _('Ghi nhận tài sản thuê TC — %(n)s', n=rec.name),
                'line_ids': [
                    (0, 0, {'account_id': rec.account_asset_id.id,
                            'partner_id': rec.partner_id.id,
                            'name': _('TS thuê TC %(n)s', n=rec.name),
                            'debit': rec.amount_financed, 'credit': 0.0}),
                    (0, 0, {'account_id': rec.account_liability_id.id,
                            'partner_id': rec.partner_id.id,
                            'name': _('Nợ gốc thuê TC %(n)s', n=rec.name),
                            'debit': 0.0, 'credit': rec.amount_financed}),
                ],
            })
            move.action_post()
            rec.recognition_move_id = move
            rec.message_post(body=_(
                'Đã ghi nhận tài sản thuê TC: %(a)s (bút toán %(m)s).',
                a='{:,.0f}'.format(rec.amount_financed), m=move.name))
        return True

    def action_post_derecognition(self):
        """Cho thuê lại TÀI CHÍNH: Nợ Phải thu thuê TC / Có TK tài sản
        (chuyển giao tài sản sang khoản phải thu khi bàn giao)."""
        for rec in self:
            if rec.direction != 'out' or rec.lease_type != 'finance':
                raise UserError(_(
                    'Bút toán chuyển giao chỉ áp dụng HĐ CHO THUÊ LẠI '
                    'TÀI CHÍNH.'))
            if rec.derecognition_move_id:
                raise UserError(_(
                    'Đã có bút toán chuyển giao (%(m)s).',
                    m=rec.derecognition_move_id.name))
            if not (rec.journal_id and rec.account_receivable_finance_id
                    and rec.account_asset_id):
                raise UserError(_(
                    'Khai đủ Sổ nhật ký + TK phải thu thuê TC + TK tài '
                    'sản (tab Kế toán) trước.'))
            move = self.env['account.move'].create({
                'move_type': 'entry',
                'journal_id': rec.journal_id.id,
                'date': rec.date_start,
                'ref': _('Chuyển giao TS cho thuê TC — %(n)s', n=rec.name),
                'line_ids': [
                    (0, 0, {'account_id':
                            rec.account_receivable_finance_id.id,
                            'partner_id': rec.partner_id.id,
                            'name': _('Phải thu thuê TC %(n)s', n=rec.name),
                            'debit': rec.amount_financed, 'credit': 0.0}),
                    (0, 0, {'account_id': rec.account_asset_id.id,
                            'partner_id': rec.partner_id.id,
                            'name': _('Chuyển giao TS %(n)s', n=rec.name),
                            'debit': 0.0, 'credit': rec.amount_financed}),
                ],
            })
            move.action_post()
            rec.derecognition_move_id = move
            rec.message_post(body=_(
                'Đã chuyển giao tài sản sang phải thu thuê TC: %(a)s '
                '(bút toán %(m)s).',
                a='{:,.0f}'.format(rec.amount_financed), m=move.name))
        return True

    # ------------------------------------------------------------------
    # Khấu hao (đi thuê tài chính) — Phase 2
    # ------------------------------------------------------------------
    @api.depends('depreciation_line_ids.amount',
                 'depreciation_line_ids.move_id', 'amount_financed')
    def _compute_depreciation_totals(self):
        for rec in self:
            posted = rec.depreciation_line_ids.filtered('move_id')
            rec.depreciated_total = sum(posted.mapped('amount'))
            rec.depreciation_remaining = (
                rec.amount_financed - rec.depreciated_total
                if rec.lease_type == 'finance' and rec.direction == 'in'
                else 0.0)

    def action_generate_depreciation(self):
        """Sinh lịch khấu hao đường thẳng theo tháng (chưa ghi sổ)."""
        for rec in self:
            if rec.direction != 'in' or rec.lease_type != 'finance':
                raise UserError(_(
                    'Khấu hao chỉ áp dụng HĐ ĐI THUÊ TÀI CHÍNH.'))
            if not rec.recognition_move_id:
                raise UserError(_(
                    'Ghi nhận tài sản thuê TC trước khi lập lịch '
                    'khấu hao.'))
            posted = rec.depreciation_line_ids.filtered('move_id')
            if posted:
                raise UserError(_(
                    'Đã có %(n)s kỳ khấu hao ghi sổ — không tạo lại '
                    'lịch được.', n=len(posted)))
            rec.depreciation_line_ids.unlink()
            months = rec.depreciation_months or (
                rec.n_periods * int(rec.period_months))
            if months <= 0:
                raise UserError(_('Số tháng khấu hao phải lớn hơn 0.'))
            per = rec.amount_financed / months
            vals, total = [], 0.0
            for i in range(1, months + 1):
                amount = (rec.amount_financed - total
                          if i == months else per)
                total += amount
                # cuối tháng thứ i kể từ ngày bắt đầu
                d = (rec.date_start + relativedelta(months=i, day=1)
                     - relativedelta(days=1))
                vals.append({'contract_id': rec.id, 'sequence': i,
                             'date': d, 'amount': amount})
            self.env['re.lease.depreciation.line'].create(vals)
            rec.message_post(body=_(
                'Đã tạo lịch khấu hao %(m)s tháng × %(a)s.',
                m=months, a='{:,.0f}'.format(per)))
        return True

    def action_post_depreciation_due(self):
        """Ghi sổ các kỳ khấu hao đã đến hạn (date ≤ hôm nay)."""
        today = fields.Date.context_today(self)
        for rec in self:
            if not (rec.account_depreciation_expense_id
                    and rec.account_depreciation_id and rec.journal_id):
                raise UserError(_(
                    'Khai đủ Sổ nhật ký + TK chi phí khấu hao + TK hao '
                    'mòn lũy kế trước.'))
            due = rec.depreciation_line_ids.filtered(
                lambda l: not l.move_id and l.date <= today)
            for line in due:
                line._post_move()
            if due:
                rec.message_post(body=_(
                    'Đã ghi sổ %(n)s kỳ khấu hao đến hạn.', n=len(due)))
        return True

    @api.model
    def _cron_post_depreciation(self):
        """Cron hằng tháng: ghi sổ khấu hao đến hạn cho HĐ hiệu lực
        (chỉ HĐ đã khai đủ tài khoản — thiếu thì bỏ qua, không lỗi)."""
        contracts = self.search([
            ('state', '=', 'active'), ('direction', '=', 'in'),
            ('lease_type', '=', 'finance')])
        for rec in contracts:
            if (rec.account_depreciation_expense_id
                    and rec.account_depreciation_id and rec.journal_id):
                rec.action_post_depreciation_due()

    def action_view_child_leases(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('HĐ cho thuê lại — %(n)s', n=self.name),
            'res_model': 're.lease.contract',
            'view_mode': 'list,form',
            'domain': [('parent_lease_id', '=', self.id)],
            'context': {'default_parent_lease_id': self.id,
                        'default_direction': 'out'},
        }


class ReLeaseAsset(models.Model):
    _name = 're.lease.asset'
    _description = 'Tài sản thuê'
    _order = 'contract_id, id'

    contract_id = fields.Many2one(
        're.lease.contract', string='HĐ thuê', required=True,
        ondelete='cascade', index=True)
    name = fields.Char(string='Tài sản', required=True,
                       help='Vd "Cẩu tháp QTZ63", "Máy đào PC200".')
    serial = fields.Char(string='Số serial / khung')
    quantity = fields.Float(string='Số lượng', default=1.0)
    date_start = fields.Date(
        string='Bắt đầu thuê',
        help='Ngày tài sản này BẮT ĐẦU tính tiền thuê. Bỏ trống = theo '
             'ngày bắt đầu HĐ. Có thể muộn hơn ngày ký HĐ (tài sản chưa '
             'cần dùng ngay).')
    date_end = fields.Date(
        string='Kết thúc thuê',
        help='Ngày tài sản này KẾT THÚC thuê. Bỏ trống = theo HĐ.')
    rent_unit_price = fields.Monetary(
        string='Đơn giá thuê',
        help='Đơn giá thuê / kỳ cho 1 đơn vị tài sản (trước thuế).')
    rent_subtotal = fields.Monetary(
        string='Số tiền thuê', compute='_compute_rent_subtotal',
        store=True, help='= Đơn giá thuê × Số lượng.')
    value = fields.Monetary(
        string='Giá trị tài sản',
        help='Giá trị tài sản (tham khảo / bảo hiểm).')
    note = fields.Char(string='Ghi chú')
    currency_id = fields.Many2one(
        related='contract_id.currency_id', store=True)
    company_id = fields.Many2one(
        related='contract_id.company_id', store=True)

    @api.depends('rent_unit_price', 'quantity')
    def _compute_rent_subtotal(self):
        for line in self:
            line.rent_subtotal = line.rent_unit_price * (line.quantity or 0.0)
