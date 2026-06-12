# -*- coding: utf-8 -*-
"""
Hợp đồng nhà thầu (rp.contract) — entity lõi.

Sau khi đấu thầu, Chủ đầu tư/Tổng thầu ký HĐ với Nhà thầu cho 1 Gói thầu.
HĐ ghi nhận giá trị, lịch thanh toán, khối lượng (BOQ optional), bảo lãnh.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class RpContract(models.Model):
    _name = 'rp.contract'
    _description = 'Hợp đồng nhà thầu'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'contract_date desc, id desc'

    # ----- Identity ------------------------------------------------------
    name = fields.Char(
        string='Số HĐ', required=True, copy=False, tracking=True,
        help='Số hợp đồng nhà thầu (nhập tay).')
    code = fields.Char(string='Mã HĐ', copy=False)
    contract_date = fields.Date(
        string='Ngày ký', tracking=True,
        default=fields.Date.context_today)
    date_start = fields.Date(string='Ngày khởi công')
    date_end = fields.Date(string='Ngày hoàn thành dự kiến')

    # ----- Linking -------------------------------------------------------
    tender_package_id = fields.Many2one(
        'rp.tender.package', string='Gói thầu', required=True,
        ondelete='restrict', tracking=True, index=True)
    contractor_id = fields.Many2one(
        'res.partner', string='Nhà thầu', required=True, tracking=True,
        ondelete='restrict', index=True,
        domain="[('is_company', '=', True)]",
        help='Nhà thầu — chuẩn Odoo dùng res.partner. Dropdown hiển '
             'thị tất cả công ty (is_company=True); khi pick lần đầu '
             'sẽ auto-flag is_contractor=True trên partner đó.')

    @api.onchange('contractor_id')
    def _onchange_contractor_flag(self):
        # Auto-flag is_contractor khi pick partner làm nhà thầu.
        if self.contractor_id and not self.contractor_id.is_contractor:
            self.contractor_id.is_contractor = True

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        # Auto-flag is_contractor=True trên partner khi tạo HĐ
        # (onchange chỉ fire ở UI, không qua RPC/import).
        for rec in recs:
            if rec.contractor_id and not rec.contractor_id.is_contractor:
                rec.contractor_id.is_contractor = True
        return recs

    def write(self, vals):
        res = super().write(vals)
        if vals.get('contractor_id'):
            for rec in self:
                if rec.contractor_id and not rec.contractor_id.is_contractor:
                    rec.contractor_id.is_contractor = True
        return res
    project_id = fields.Many2one(
        related='tender_package_id.project_id', store=True, readonly=True)
    subzone_ids = fields.Many2many(
        're.subzone', string='Khu vực',
        compute='_compute_subzone_ids', store=True,
        help='Các khu vực được cover (suy từ Hạng mục trong Gói thầu).')
    structure_ids = fields.Many2many(
        'rp.structure',
        'rp_contract_structure_rel', 'contract_id', 'structure_id',
        string='Hạng mục cover',
        compute='_compute_structure_ids', store=True,
        help='Hạng mục được HĐ này thực hiện — suy từ Hạng mục trong '
             'Gói thầu. Dùng để render HĐ trên Gantt dưới mỗi hạng mục.')

    # ----- Money ---------------------------------------------------------
    currency_id = fields.Many2one(
        related='tender_package_id.currency_id', store=True, readonly=True)
    contract_value_pretax = fields.Monetary(
        string='Giá trị HĐ (trước thuế)', required=True, tracking=True)
    vat_rate = fields.Float(
        string='Thuế suất VAT (%)', default=8.0, digits=(5, 2),
        help='Thuế suất GTGT áp dụng cho HĐ. VN xây dựng thường 8% hoặc 10%.')
    vat_amount = fields.Monetary(
        string='Tiền VAT', compute='_compute_amounts', store=True)
    contract_value_total = fields.Monetary(
        string='Giá trị HĐ (sau thuế)', compute='_compute_amounts', store=True)

    advance_percent = fields.Float(
        string='Tạm ứng (%)', digits=(5, 2),
        help='Tỷ lệ tạm ứng theo HĐ. VN thường 10-30%.')
    amount_advance = fields.Monetary(
        string='Số tiền tạm ứng', compute='_compute_amounts', store=True)
    retention_percent = fields.Float(
        string='Giữ lại bảo hành (%)', digits=(5, 2), default=5.0,
        help='Tỷ lệ giữ lại bảo hành (retention). VN thường 5%.')
    amount_retention = fields.Monetary(
        string='Số tiền giữ lại', compute='_compute_amounts', store=True)

    # ----- Progress ------------------------------------------------------
    amount_paid = fields.Monetary(
        string='Đã thanh toán', compute='_compute_payment_stats', store=True)
    amount_remaining = fields.Monetary(
        string='Còn phải trả', compute='_compute_payment_stats', store=True)
    payment_progress = fields.Float(
        string='Tiến độ thanh toán (%)',
        compute='_compute_payment_stats', store=True, digits=(5, 2))

    # ----- Guarantees (v1.1: NH = M2O res.partner is_bank=True;
    # FK rf.bank.guarantee khi module đó ship) -----------------------
    guarantee_performance_no = fields.Char(string='Số BL thực hiện HĐ')
    guarantee_performance_bank_id = fields.Many2one(
        'res.partner', string='NH bảo lãnh (TH HĐ)',
        domain="[('is_bank', '=', True)]")
    guarantee_performance_amount = fields.Monetary(
        string='Số tiền BL thực hiện HĐ')
    guarantee_performance_expiry = fields.Date(string='Hết hạn BL TH HĐ')

    guarantee_advance_no = fields.Char(string='Số BL tạm ứng')
    guarantee_advance_bank_id = fields.Many2one(
        'res.partner', string='NH bảo lãnh (tạm ứng)',
        domain="[('is_bank', '=', True)]")
    guarantee_advance_amount = fields.Monetary(string='Số tiền BL tạm ứng')
    guarantee_advance_expiry = fields.Date(string='Hết hạn BL tạm ứng')

    guarantee_warranty_no = fields.Char(string='Số BL bảo hành')
    guarantee_warranty_bank_id = fields.Many2one(
        'res.partner', string='NH bảo lãnh (bảo hành)',
        domain="[('is_bank', '=', True)]")
    guarantee_warranty_amount = fields.Monetary(string='Số tiền BL bảo hành')
    guarantee_warranty_expiry = fields.Date(string='Hết hạn BL bảo hành')

    # ----- Lines / milestones / amendments -------------------------------
    line_ids = fields.One2many(
        'rp.contract.line', 'contract_id', string='Khối lượng (BOQ)')
    line_count = fields.Integer(compute='_compute_counts')
    line_total = fields.Monetary(
        string='Σ khối lượng', compute='_compute_amounts', store=True)
    payment_milestone_ids = fields.One2many(
        'rp.contract.payment.milestone', 'contract_id',
        string='Lịch thanh toán')
    payment_milestone_count = fields.Integer(compute='_compute_counts')
    amendment_ids = fields.One2many(
        'rp.contract.amendment', 'contract_id', string='Phụ lục')
    amendment_count = fields.Integer(compute='_compute_counts')

    # ----- State machine -------------------------------------------------
    state = fields.Selection(
        [('draft', 'Nháp'),
         ('signed', 'Đã ký'),
         ('executing', 'Đang thực hiện'),
         ('completed', 'Đã hoàn thành'),
         ('terminated', 'Đã chấm dứt')],
        string='Trạng thái', default='draft', required=True, tracking=True)

    note = fields.Text(string='Ghi chú')
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', string='Công ty', required=True,
        default=lambda self: self.env.company)

    # ======================================================================
    # Compute
    # ======================================================================
    @api.depends('tender_package_id.line_ids.subzone_id')
    def _compute_subzone_ids(self):
        for rec in self:
            rec.subzone_ids = rec.tender_package_id.line_ids.mapped(
                'subzone_id')

    @api.depends('tender_package_id.line_ids.structure_id')
    def _compute_structure_ids(self):
        for rec in self:
            rec.structure_ids = rec.tender_package_id.line_ids.mapped(
                'structure_id')

    @api.depends('contract_value_pretax', 'vat_rate', 'advance_percent',
                 'retention_percent', 'line_ids.amount')
    def _compute_amounts(self):
        for rec in self:
            rec.vat_amount = rec.contract_value_pretax * rec.vat_rate / 100.0
            rec.contract_value_total = (
                rec.contract_value_pretax + rec.vat_amount)
            rec.amount_advance = (
                rec.contract_value_total * rec.advance_percent / 100.0)
            rec.amount_retention = (
                rec.contract_value_total * rec.retention_percent / 100.0)
            rec.line_total = sum(rec.line_ids.mapped('amount'))

    @api.depends('payment_milestone_ids.amount',
                 'payment_milestone_ids.state', 'contract_value_total')
    def _compute_payment_stats(self):
        for rec in self:
            paid = sum(rec.payment_milestone_ids.filtered(
                lambda m: m.state == 'paid').mapped('amount'))
            rec.amount_paid = paid
            rec.amount_remaining = rec.contract_value_total - paid
            rec.payment_progress = (
                paid * 100.0 / rec.contract_value_total
                if rec.contract_value_total else 0.0)

    @api.depends('line_ids', 'payment_milestone_ids', 'amendment_ids')
    def _compute_counts(self):
        for rec in self:
            rec.line_count = len(rec.line_ids)
            rec.payment_milestone_count = len(rec.payment_milestone_ids)
            rec.amendment_count = len(rec.amendment_ids)

    # ======================================================================
    # Constraints
    # ======================================================================
    @api.constrains('contract_value_pretax')
    def _check_value(self):
        for rec in self:
            if rec.contract_value_pretax <= 0:
                raise ValidationError(_("Giá trị HĐ trước thuế phải > 0."))

    @api.constrains('vat_rate', 'advance_percent', 'retention_percent')
    def _check_percents(self):
        for rec in self:
            if rec.vat_rate < 0 or rec.vat_rate > 100:
                raise ValidationError(_("Thuế suất VAT 0–100%."))
            if rec.advance_percent < 0 or rec.advance_percent > 100:
                raise ValidationError(_("Tạm ứng 0–100%."))
            if rec.retention_percent < 0 or rec.retention_percent > 50:
                raise ValidationError(_("Giữ lại bảo hành 0–50%."))

    def _check_line_total_at_sign(self):
        """Khi ký HĐ: nếu đã nhập BOQ thì Σ phải ≈ giá trị HĐ trước thuế."""
        for rec in self:
            if rec.line_ids:
                diff = abs(rec.line_total - rec.contract_value_pretax)
                if diff > 1:
                    raise UserError(_(
                        "Tổng khối lượng (%(t)s) khác giá trị HĐ trước thuế "
                        "(%(v)s). Điều chỉnh BOQ hoặc giá trị HĐ trước khi ký.",
                        t=rec.line_total, v=rec.contract_value_pretax))

    @api.constrains('contractor_id', 'tender_package_id')
    def _check_contractor_company(self):
        for rec in self:
            # Nếu nhà thầu là partner shared multi-company (company_id
            # = False), bỏ qua check — partner dùng được mọi company.
            if (rec.contractor_id and rec.tender_package_id
                    and rec.contractor_id.company_id
                    and rec.contractor_id.company_id
                    != rec.tender_package_id.company_id):
                raise ValidationError(_(
                    "Nhà thầu phải cùng công ty với Gói thầu."))

    # ======================================================================
    # State machine
    # ======================================================================
    def action_sign(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_("Chỉ ký được HĐ ở trạng thái Nháp."))
            if not rec.contract_value_pretax:
                raise UserError(_("Cần nhập giá trị HĐ trước khi ký."))
            rec._check_line_total_at_sign()
            rec.state = 'signed'

    def action_start_execution(self):
        for rec in self:
            if rec.state != 'signed':
                raise UserError(_("Chỉ khởi công HĐ đã ký."))
            rec.state = 'executing'

    def action_complete(self):
        for rec in self:
            if rec.state not in ('signed', 'executing'):
                raise UserError(_(
                    "Chỉ hoàn thành HĐ đang ký/thực hiện."))
            # Cảnh báo nếu chưa thanh toán đủ
            if rec.amount_remaining > 1:
                rec.message_post(body=_(
                    "Đánh dấu hoàn thành khi còn dư phải trả: %(r)s.",
                    r=rec.amount_remaining))
            rec.state = 'completed'

    def action_terminate(self):
        for rec in self:
            if rec.state in ('completed', 'terminated'):
                raise UserError(_("HĐ đã đóng."))
            rec.state = 'terminated'

    def action_reset_draft(self):
        for rec in self:
            if rec.state not in ('terminated',):
                raise UserError(_(
                    "Chỉ HĐ đã chấm dứt mới đưa về Nháp được."))
            rec.state = 'draft'

    # ======================================================================
    # Guards
    # ======================================================================
    def unlink(self):
        for rec in self:
            if rec.state not in ('draft',):
                raise UserError(_(
                    "Không xoá được HĐ '%s' khi không ở Nháp. "
                    "Dùng Chấm dứt để giữ vết.", rec.name))
        return super().unlink()

    # ======================================================================
    # Smart-button actions
    # ======================================================================
    def action_view_milestones(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Lịch thanh toán'),
            'res_model': 'rp.contract.payment.milestone',
            'view_mode': 'list,form',
            'domain': [('contract_id', '=', self.id)],
            'context': {'default_contract_id': self.id},
        }

    def action_view_amendments(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Phụ lục'),
            'res_model': 'rp.contract.amendment',
            'view_mode': 'list,form',
            'domain': [('contract_id', '=', self.id)],
            'context': {'default_contract_id': self.id},
        }
