# -*- coding: utf-8 -*-
"""Bảo lãnh hợp đồng nhà thầu — sổ đăng ký BL nhận từ nhà thầu phụ.

Tổng thầu (mình) là **bên thụ hưởng**: nhà thầu phụ nộp bảo lãnh (do NH
hoặc công ty bảo hiểm của họ phát hành) để bảo đảm thực hiện hợp đồng /
hoàn tạm ứng / bảo hành. KHÔNG ăn hạn mức tín dụng của mình, KHÔNG phát
sinh phí cho mình (nhà thầu phụ trả phí) → tách hẳn khỏi Quản lý Vay.

Căn cứ: Luật Đấu thầu 2023 (bảo đảm thực hiện HĐ 2–10% giá trị HĐ, hiệu
lực đến khi hoàn thành nghĩa vụ / chuyển bảo hành) + Thông tư
11/2022/TT-NHNN (bảo lãnh ngân hàng).
"""
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

EXPIRY_ALERT_DAYS = 30  # ngưỡng cảnh báo "sắp hết hạn" (mặc định)


class RpContractGuarantee(models.Model):
    _name = 'rp.contract.guarantee'
    _description = 'Bảo lãnh hợp đồng nhà thầu'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_expiry, id desc'

    # ---- Định danh -------------------------------------------------
    name = fields.Char(
        string='Số chứng thư / bảo lãnh', required=True, tracking=True,
        help='Số thư bảo lãnh / chứng thư do bên phát hành cấp.')
    guarantee_type = fields.Selection(
        [('performance', 'Thực hiện hợp đồng'),
         ('advance',     'Hoàn tạm ứng'),
         ('warranty',    'Bảo hành'),
         ('bid',         'Dự thầu')],
        string='Loại bảo lãnh', required=True, default='performance',
        tracking=True)
    security_form = fields.Selection(
        [('bank_guarantee', 'Thư bảo lãnh ngân hàng'),
         ('insurance',      'Bảo hiểm bảo lãnh'),
         ('deposit',        'Đặt cọc'),
         ('escrow',         'Ký quỹ')],
        string='Hình thức bảo đảm', required=True, default='bank_guarantee',
        tracking=True,
        help='Luật Đấu thầu 2023 chấp nhận: thư BL ngân hàng, giấy '
             'chứng nhận bảo hiểm bảo lãnh, đặt cọc.')

    # ---- Hợp đồng & các bên ---------------------------------------
    contract_id = fields.Many2one(
        'rp.contract', string='Hợp đồng nhà thầu', required=True,
        ondelete='cascade', tracking=True)
    contractor_id = fields.Many2one(
        'res.partner', string='Nhà thầu (bên được bảo lãnh)',
        related='contract_id.contractor_id', store=True, readonly=True)
    project_id = fields.Many2one(
        related='contract_id.project_id', store=True, readonly=True,
        string='Dự án')
    beneficiary_partner_id = fields.Many2one(
        'res.partner', string='Bên thụ hưởng',
        default=lambda self: self.env.company.partner_id,
        help='Bên nhận bảo lãnh — thường là công ty mình (tổng thầu).')
    issuer_partner_id = fields.Many2one(
        'res.partner', string='Bên phát hành (NH / bảo hiểm)',
        tracking=True,
        help='Ngân hàng hoặc công ty bảo hiểm phát hành bảo lãnh cho '
             'nhà thầu. Bỏ trống nếu hình thức là đặt cọc / ký quỹ.')

    # ---- Giá trị ---------------------------------------------------
    amount = fields.Monetary(
        string='Giá trị bảo lãnh', required=True, tracking=True)
    currency_id = fields.Many2one(
        'res.currency', required=True,
        default=lambda self: self.env.company.currency_id)
    contract_value = fields.Monetary(
        related='contract_id.contract_value_total', store=True,
        readonly=True, string='Giá trị HĐ')
    amount_percent = fields.Float(
        string='% giá trị HĐ', compute='_compute_amount_percent',
        store=True, digits=(5, 2))
    percent_warning = fields.Boolean(
        string='Ngoài khoảng 2–10%', compute='_compute_amount_percent',
        store=True,
        help='Luật Đấu thầu 2023: bảo đảm thực hiện HĐ thường 2–10% '
             'giá trị hợp đồng.')

    # ---- Thời hạn --------------------------------------------------
    date_issue = fields.Date(string='Ngày phát hành', tracking=True)
    date_effective = fields.Date(string='Ngày hiệu lực', tracking=True)
    date_expiry = fields.Date(
        string='Ngày hết hạn', required=True, tracking=True,
        help='Bảo lãnh có hiệu lực đến khi nhà thầu hoàn thành nghĩa '
             'vụ / chuyển bảo hành — gia hạn HĐ phải gia hạn BL.')
    days_to_expiry = fields.Integer(
        string='Còn (ngày)', compute='_compute_expiry', store=True)
    expiry_status = fields.Selection(
        [('valid',    'Còn hiệu lực'),
         ('expiring', 'Sắp hết hạn'),
         ('expired',  'Đã hết hạn')],
        string='Tình trạng hạn', compute='_compute_expiry', store=True)

    # ---- Điều khoản ------------------------------------------------
    is_unconditional = fields.Boolean(
        string='Vô điều kiện',
        help='Bảo lãnh vô điều kiện — NH trả ngay khi có yêu cầu hợp lệ, '
             'không cần chứng minh vi phạm.')
    is_irrevocable = fields.Boolean(string='Không hủy ngang')
    terms = fields.Text(string='Điều khoản / diễn giải')

    # ---- Vòng đời --------------------------------------------------
    state = fields.Selection(
        [('draft',     'Nháp'),
         ('active',    'Hiệu lực'),
         ('released',  'Đã hoàn trả'),
         ('claimed',   'Đã yêu cầu thanh toán'),
         ('cancelled', 'Hủy')],
        string='Trạng thái', default='draft', required=True, tracking=True)
    date_released = fields.Date(
        string='Ngày hoàn trả', readonly=True, tracking=True)
    claim_date = fields.Date(
        string='Ngày yêu cầu thanh toán', readonly=True, tracking=True)
    claim_amount = fields.Monetary(
        string='Số tiền yêu cầu', readonly=True)
    claim_reason = fields.Text(string='Lý do yêu cầu thanh toán')

    # ---- Phụ lục & tài liệu ---------------------------------------
    amendment_ids = fields.One2many(
        'rp.contract.guarantee.amendment', 'guarantee_id',
        string='Phụ lục gia hạn / điều chỉnh')
    amendment_count = fields.Integer(compute='_compute_amendment_count')
    attachment_ids = fields.Many2many(
        'ir.attachment', 'rp_contract_guarantee_att_rel',
        'guarantee_id', 'attachment_id',
        string='Tài liệu đính kèm',
        help='Thư bảo lãnh gốc (scan/PDF), phụ lục gia hạn…')
    note = fields.Char(string='Ghi chú')
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company)

    # ---- Computes --------------------------------------------------
    @api.depends('amount', 'contract_value')
    def _compute_amount_percent(self):
        for rec in self:
            if rec.contract_value:
                pct = rec.amount / rec.contract_value * 100.0
            else:
                pct = 0.0
            rec.amount_percent = pct
            # chỉ cảnh báo với BL thực hiện HĐ (loại có ngưỡng luật định)
            rec.percent_warning = (
                rec.guarantee_type == 'performance'
                and rec.contract_value
                and (pct < 2.0 or pct > 10.0))

    @api.depends('date_expiry', 'state')
    def _compute_expiry(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if not rec.date_expiry:
                rec.days_to_expiry = 0
                rec.expiry_status = False
                continue
            delta = (rec.date_expiry - today).days
            rec.days_to_expiry = delta
            if rec.state != 'active':
                rec.expiry_status = False
            elif delta < 0:
                rec.expiry_status = 'expired'
            elif delta <= EXPIRY_ALERT_DAYS:
                rec.expiry_status = 'expiring'
            else:
                rec.expiry_status = 'valid'

    @api.depends('amendment_ids')
    def _compute_amendment_count(self):
        for rec in self:
            rec.amendment_count = len(rec.amendment_ids)

    # ---- Onchange --------------------------------------------------
    @api.onchange('guarantee_type', 'contract_id')
    def _onchange_prefill_expiry(self):
        """Gợi ý ngày hết hạn theo loại BL + ngày HĐ (sửa được)."""
        c = self.contract_id
        if not c:
            return
        if self.guarantee_type == 'warranty' and c.date_end:
            # BL bảo hành: từ hoàn thành + kỳ bảo hành (mặc định 12 tháng)
            self.date_effective = c.date_end
            self.date_expiry = c.date_end + relativedelta(months=12)
        elif c.date_start and c.date_end:
            self.date_effective = c.date_start
            self.date_expiry = c.date_end

    # ---- Actions vòng đời ------------------------------------------
    def action_activate(self):
        for rec in self:
            if rec.state not in ('draft',):
                raise UserError(_("Chỉ kích hoạt được bảo lãnh ở trạng "
                                  "thái Nháp."))
            if rec.security_form in ('bank_guarantee', 'insurance') \
                    and not rec.issuer_partner_id:
                raise UserError(_(
                    "Bảo lãnh hình thức '%s' cần khai Bên phát hành "
                    "(NH / bảo hiểm).")
                    % dict(rec._fields['security_form'].selection).get(
                        rec.security_form))
            rec.state = 'active'

    def action_release(self):
        for rec in self:
            if rec.state != 'active':
                raise UserError(_("Chỉ hoàn trả được bảo lãnh đang hiệu "
                                  "lực."))
            rec.state = 'released'
            rec.date_released = fields.Date.context_today(rec)

    def action_cancel(self):
        for rec in self:
            rec.state = 'cancelled'

    def action_set_draft(self):
        for rec in self:
            rec.state = 'draft'
            rec.date_released = False

    def action_open_claim_wizard(self):
        self.ensure_one()
        if self.state != 'active':
            raise UserError(_(
                "Chỉ yêu cầu thanh toán bảo lãnh đang hiệu lực."))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Yêu cầu thanh toán bảo lãnh'),
            'res_model': 'rp.contract.guarantee.claim.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_guarantee_id': self.id,
                        'default_claim_amount': self.amount},
        }

    def action_view_amendments(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'target': 'new',
            'name': _('Phụ lục bảo lãnh'),
            'res_model': 'rp.contract.guarantee.amendment',
            'view_mode': 'list,form',
            'domain': [('guarantee_id', '=', self.id)],
            'context': {'default_guarantee_id': self.id},
        }

    # ---- Cron cảnh báo hết hạn -------------------------------------
    @api.model
    def _cron_expiry_alert(self):
        """Đăng activity nhắc các BL sắp/đã hết hạn cho người phụ trách."""
        today = fields.Date.context_today(self)
        limit = today + relativedelta(days=EXPIRY_ALERT_DAYS)
        due = self.search([
            ('state', '=', 'active'),
            ('date_expiry', '<=', limit),
        ])
        for rec in due:
            # tránh spam: chỉ tạo activity nếu chưa có activity mở
            if rec.activity_ids.filtered(
                    lambda a: a.activity_type_id
                    == self.env.ref('mail.mail_activity_data_todo',
                                    raise_if_not_found=False)):
                continue
            overdue = rec.date_expiry < today
            rec.activity_schedule(
                'mail.mail_activity_data_todo',
                date_deadline=rec.date_expiry,
                summary=_("Bảo lãnh %s %s") % (
                    rec.name,
                    _("ĐÃ HẾT HẠN") if overdue else _("sắp hết hạn")),
                note=_("BL %(t)s của HĐ %(c)s (nhà thầu %(nt)s) "
                       "hết hạn %(d)s — yêu cầu nhà thầu gia hạn hoặc "
                       "xử lý.",
                       t=dict(rec._fields['guarantee_type'].selection).get(
                           rec.guarantee_type),
                       c=rec.contract_id.name or '',
                       nt=rec.contractor_id.name or '',
                       d=rec.date_expiry),
                user_id=(rec.contract_id.create_uid.id
                         or self.env.uid))
