# -*- coding: utf-8 -*-
"""HĐ thi công ĐẦU RA — tổng thầu ký với Chủ đầu tư.

Đối xứng với rp.contract (HĐ đầu vào thuê nhà thầu phụ). Tổng hợp
sản lượng nghiệm thu với CĐT + tiền CĐT đã trả → khoản phải thu
(quyền đòi nợ) — nguồn TSBĐ động cho borrowing base.
"""
from odoo import api, fields, models
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
    payment_ids = fields.One2many(
        'rp.owner.payment', 'contract_id', string='Thanh toán của CĐT')
    acceptance_count = fields.Integer(compute='_compute_totals')
    payment_count = fields.Integer(compute='_compute_totals')

    # --- Tổng hợp phải thu ---
    accepted_to_date = fields.Monetary(
        string='Sản lượng nghiệm thu lũy kế',
        compute='_compute_totals', store=True,
        help='Σ giá trị các BBNT đã được CĐT duyệt (trước thuế).')
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
                 'acceptance_ids.state',
                 'payment_ids.amount',
                 'contract_value_pretax')
    def _compute_totals(self):
        for rec in self:
            approved = rec.acceptance_ids.filtered(
                lambda a: a.state == 'approved')
            rec.acceptance_count = len(rec.acceptance_ids)
            rec.payment_count = len(rec.payment_ids)
            rec.accepted_to_date = sum(
                approved.mapped('amount_this_period'))
            rec.paid_to_date = sum(rec.payment_ids.mapped('amount'))
            rec.receivable = rec.accepted_to_date - rec.paid_to_date
            rec.progress_percent = (
                rec.accepted_to_date / rec.contract_value_pretax * 100.0
                if rec.contract_value_pretax else 0.0)

    @api.constrains('contract_value_pretax')
    def _check_value(self):
        for rec in self:
            if rec.contract_value_pretax <= 0:
                raise ValidationError('Giá trị HĐ phải > 0.')

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
