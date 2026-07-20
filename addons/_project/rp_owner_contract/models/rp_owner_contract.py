# -*- coding: utf-8 -*-
"""HĐ thi công ĐẦU RA — tổng thầu ký với Chủ đầu tư.

Đối xứng với rp.contract (HĐ đầu vào thuê nhà thầu phụ). Tổng hợp
sản lượng nghiệm thu với CĐT + tiền CĐT đã trả → khoản phải thu
(quyền đòi nợ) — nguồn TSBĐ động cho borrowing base.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class RpOwnerContract(models.Model):
    _name = 'rp.owner.contract'
    _description = 'HĐ thi công với Chủ đầu tư (đầu ra)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_contract desc, id desc'

    name = fields.Char(
        string='Số HĐ', required=True, copy=False, tracking=True)
    project_id = fields.Many2one(
        're.project', string='Dự án', required=True,
        ondelete='restrict', index=True, tracking=True)
    owner_id = fields.Many2one(
        'res.partner', string='Chủ đầu tư', required=True,
        ondelete='restrict', tracking=True,
        domain="[('is_company', '=', True)]")
    date_contract = fields.Date(string='Ngày ký', tracking=True)
    date_start = fields.Date(string='Ngày khởi công')
    date_end = fields.Date(string='Ngày hoàn thành dự kiến')

    contract_value_pretax = fields.Monetary(
        string='Giá trị HĐ (trước thuế)', required=True, tracking=True)
    vat_rate = fields.Float(string='Thuế suất VAT (%)', default=8.0)
    contract_value_total = fields.Monetary(
        string='Giá trị HĐ (sau thuế)',
        compute='_compute_value_total', store=True)

    state = fields.Selection(
        [('draft', 'Nháp'),
         ('signed', 'Đã ký'),
         ('executing', 'Đang thi công'),
         ('completed', 'Hoàn thành'),
         ('terminated', 'Chấm dứt')],
        string='Trạng thái', default='draft', required=True, tracking=True)

    acceptance_ids = fields.One2many(
        'rp.owner.acceptance', 'contract_id', string='BBNT với CĐT')
    ipc_ids = fields.One2many(
        'rp.owner.ipc', 'contract_id', string='IPC (hồ sơ thanh toán)')
    ipc_count = fields.Integer(compute='_compute_ipc')
    payment_ids = fields.One2many(
        'rp.owner.payment', 'contract_id', string='Thanh toán của CĐT')
    milestone_ids = fields.One2many(
        'rp.owner.payment.milestone', 'contract_id',
        string='Kế hoạch thanh toán (theo tiến độ)')
    invoice_ids = fields.One2many(
        'account.move', 'owner_contract_id', string='Hoá đơn phát hành CĐT',
        domain=[('move_type', '=', 'out_invoice')])
    acceptance_count = fields.Integer(compute='_compute_totals')
    payment_count = fields.Integer(compute='_compute_totals')
    milestone_count = fields.Integer(compute='_compute_revenue')
    invoice_count = fields.Integer(compute='_compute_revenue')

    # --- Doanh thu / phải thu (theo hoá đơn phát hành CĐT) ---
    revenue_invoiced = fields.Monetary(
        string='Doanh thu đã xuất HĐ',
        compute='_compute_revenue', store=True,
        help='Σ giá trị trước thuế các hoá đơn CĐT đã phát hành (đã vào sổ).')
    received_to_date = fields.Monetary(
        string='CĐT đã thu (theo HĐ)',
        compute='_compute_revenue', store=True)
    receivable_invoiced = fields.Monetary(
        string='Còn phải thu (theo HĐ)',
        compute='_compute_revenue', store=True,
        help='Σ còn phải trả của các hoá đơn CĐT đã phát hành.')

    # --- Điều khoản thanh toán (nguồn cho công thức Gross → Net) ---
    # MẶC ĐỊNH 0: cài module KHÔNG làm đổi số của HĐ đang chạy. Chỉ khi
    # khai báo điều khoản thật thì giảm trừ mới phát sinh.
    retention_percent = fields.Float(
        string='% giữ lại mỗi kỳ', default=0.0, tracking=True,
        help='Tỷ lệ CĐT giữ lại trên sản lượng mỗi kỳ (thường 5%). '
             'Để 0 = không giữ lại.')
    retention_cap_percent = fields.Float(
        string='Trần giữ lại (% giá trị HĐ)', default=0.0, tracking=True,
        help='Tổng giữ lại luỹ kế không vượt tỷ lệ này trên giá trị HĐ '
             '(thường 5%). Để 0 = không chặn trần.')
    advance_amount = fields.Monetary(
        string='Tạm ứng đã nhận', default=0.0, tracking=True,
        help='Giá trị tạm ứng CĐT đã cấp — sẽ được thu hồi dần qua các '
             'BBNT theo % bên dưới.')
    advance_recovery_percent = fields.Float(
        string='% thu hồi tạm ứng mỗi kỳ', default=0.0, tracking=True,
        help='Tỷ lệ khấu trừ trên sản lượng gross mỗi kỳ để thu hồi tạm '
             'ứng, dừng khi hết số dư. Để 0 = không tự thu hồi.')

    retention_held = fields.Monetary(
        string='Giữ lại đang nắm',
        compute='_compute_totals', store=True,
        help='Σ retention của các BBNT đã duyệt — tiền CĐT đang giữ, '
             'chưa đòi được. Tới mốc hoàn thì lập BBNT mới để đòi.')
    advance_balance = fields.Monetary(
        string='Số dư tạm ứng',
        compute='_compute_totals', store=True,
        help='= Tạm ứng đã nhận − Σ đã thu hồi qua các BBNT đã duyệt.')

    # --- Tổng hợp phải thu ---
    accepted_gross_to_date = fields.Monetary(
        string='Sản lượng gross lũy kế',
        compute='_compute_totals', store=True,
        help='Σ sản lượng GỘP các BBNT đã duyệt — dùng để đo tiến độ so '
             'với giá trị HĐ (retention vẫn là phần việc đã làm).')
    accepted_to_date = fields.Monetary(
        string='Sản lượng nghiệm thu lũy kế',
        compute='_compute_totals', store=True,
        help='Σ QUYỀN ĐÒI NỢ phát sinh của các BBNT đã duyệt (trước '
             'thuế) = gross − giữ lại − back-charge ± điều chỉnh. '
             'KHÔNG trừ thu hồi tạm ứng ở đây — tiền tạm ứng đã nằm '
             'trong "CĐT đã thanh toán".')
    paid_to_date = fields.Monetary(
        string='CĐT đã thanh toán',
        compute='_compute_totals', store=True,
        help='Σ tiền CĐT đã trả (tạm ứng + theo sản lượng + khác).')
    receivable = fields.Monetary(
        string='Khoản phải thu',
        compute='_compute_totals', store=True,
        help='= Sản lượng nghiệm thu lũy kế − CĐT đã trả. ÂM = CĐT đang '
             'tạm ứng trước sản lượng (bình thường đầu dự án). Đây là '
             'giá trị quyền đòi nợ dùng cho borrowing base (phần dương).')
    progress_percent = fields.Float(
        string='% sản lượng / giá trị HĐ',
        compute='_compute_totals', store=True)

    # --- Chống thế chấp TRÙNG giữa 2 cấp ---
    # TSBĐ gắn ở CẤP HĐ lấy giá trị = `receivable` (toàn bộ phải thu).
    # Khi một IPC được cầm cố RIÊNG, phần đó phải bị trừ ra khỏi cấp HĐ,
    # nếu không cùng một khoản tiền được thế chấp hai lần.
    receivable_pledged_ipc = fields.Monetary(
        string='Phải thu đã cầm cố theo IPC',
        compute='_compute_ipc', store=True,
        help='Σ quyền đòi nợ của các IPC đã được đưa vào TSBĐ riêng.')
    receivable_unpledged = fields.Monetary(
        string='Phải thu chưa cầm cố',
        compute='_compute_ipc', store=True,
        help='= Khoản phải thu − phần đã cầm cố theo IPC. ĐÂY là giá trị '
             'TSBĐ gắn ở cấp hợp đồng, để không thế chấp trùng.')

    currency_id = fields.Many2one(
        'res.currency', string='Loại tiền', required=True,
        default=lambda self: self.env.company.currency_id)
    company_id = fields.Many2one(
        'res.company', string='Công ty', required=True,
        default=lambda self: self.env.company)
    note = fields.Text(string='Ghi chú')

    _sql_constraints = [
        ('name_company_unique', 'unique(name, company_id)',
         'Số HĐ với CĐT đã tồn tại.'),
    ]

    @api.depends('contract_value_pretax', 'vat_rate')
    def _compute_value_total(self):
        for rec in self:
            rec.contract_value_total = rec.contract_value_pretax * (
                1 + (rec.vat_rate or 0.0) / 100.0)

    @api.depends('acceptance_ids.amount_this_period',
                 'acceptance_ids.amount_certified',
                 'acceptance_ids.advance_recovery',
                 'acceptance_ids.retention_amount',
                 'acceptance_ids.state',
                 'payment_ids.amount',
                 'advance_amount',
                 'contract_value_pretax')
    def _compute_totals(self):
        for rec in self:
            approved = rec.acceptance_ids.filtered(
                lambda a: a.state == 'approved')
            rec.acceptance_count = len(rec.acceptance_ids)
            rec.payment_count = len(rec.payment_ids)
            rec.accepted_gross_to_date = sum(
                approved.mapped('amount_this_period'))
            # QUYỀN ĐÒI NỢ — số chảy vào phải thu / borrowing base
            rec.accepted_to_date = sum(approved.mapped('amount_certified'))
            rec.retention_held = sum(approved.mapped('retention_amount'))
            rec.advance_balance = max(0.0, (rec.advance_amount or 0.0) - sum(
                approved.mapped('advance_recovery')))
            rec.paid_to_date = sum(rec.payment_ids.mapped('amount'))
            rec.receivable = rec.accepted_to_date - rec.paid_to_date
            # Tiến độ đo trên GROSS: retention vẫn là phần việc đã làm
            rec.progress_percent = (
                rec.accepted_gross_to_date / rec.contract_value_pretax * 100.0
                if rec.contract_value_pretax else 0.0)

    @api.depends('ipc_ids.amount_pledged', 'ipc_ids.is_pledged',
                 'ipc_ids.state', 'receivable')
    def _compute_ipc(self):
        for rec in self:
            rec.ipc_count = len(rec.ipc_ids)
            rec.receivable_pledged_ipc = sum(
                rec.ipc_ids.filtered(
                    lambda i: i.is_pledged and i.state == 'signed'
                ).mapped('amount_pledged'))
            rec.receivable_unpledged = max(
                0.0, rec.receivable - rec.receivable_pledged_ipc)

    def action_open_ipc(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('IPC — %s') % self.name,
            'res_model': 'rp.owner.ipc',
            'view_mode': 'list,form',
            'domain': [('contract_id', '=', self.id)],
            'context': {'default_contract_id': self.id},
        }

    @api.depends('invoice_ids.state', 'invoice_ids.amount_untaxed',
                 'invoice_ids.amount_total', 'invoice_ids.amount_residual',
                 'milestone_ids')
    def _compute_revenue(self):
        for rec in self:
            posted = rec.invoice_ids.filtered(lambda m: m.state == 'posted')
            rec.invoice_count = len(rec.invoice_ids)
            rec.milestone_count = len(rec.milestone_ids)
            rec.revenue_invoiced = sum(posted.mapped('amount_untaxed'))
            rec.receivable_invoiced = sum(posted.mapped('amount_residual'))
            rec.received_to_date = sum(
                posted.mapped('amount_total')) - rec.receivable_invoiced

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        recs.owner_id.filtered(
            lambda p: not p.is_project_owner).is_project_owner = True
        return recs

    @api.constrains('contract_value_pretax')
    def _check_value(self):
        for rec in self:
            if rec.contract_value_pretax <= 0:
                raise ValidationError('Giá trị HĐ phải > 0.')

    def action_view_milestones(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Kế hoạch thanh toán',
            'res_model': 'rp.owner.payment.milestone',
            'view_mode': 'list,form',
            'domain': [('contract_id', '=', self.id)],
            'context': {'default_contract_id': self.id},
        }

    def action_view_invoices(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Hoá đơn phát hành CĐT',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('owner_contract_id', '=', self.id),
                       ('move_type', '=', 'out_invoice')],
            'context': {'default_move_type': 'out_invoice',
                        'default_owner_contract_id': self.id,
                        'default_partner_id': self.owner_id.id},
        }

    # --- Workflow ---
    def action_sign(self):
        self.filtered(lambda r: r.state == 'draft').write(
            {'state': 'signed'})

    def action_execute(self):
        self.filtered(lambda r: r.state == 'signed').write(
            {'state': 'executing'})

    def action_complete(self):
        self.filtered(
            lambda r: r.state in ('signed', 'executing')).write(
            {'state': 'completed'})

    def action_terminate(self):
        self.filtered(
            lambda r: r.state not in ('completed',)).write(
            {'state': 'terminated'})

    def action_view_acceptances(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'BBNT với CĐT',
            'res_model': 'rp.owner.acceptance',
            'view_mode': 'list,form',
            'domain': [('contract_id', '=', self.id)],
            'context': {'default_contract_id': self.id},
        }

    def action_view_payments(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Thanh toán của CĐT',
            'res_model': 'rp.owner.payment',
            'view_mode': 'list,form',
            'domain': [('contract_id', '=', self.id)],
            'context': {'default_contract_id': self.id},
        }
