# -*- coding: utf-8 -*-
"""BBNT sản lượng ĐẦU RA — tổng thầu nghiệm thu VỚI Chủ đầu tư.

Mỗi BBNT = 1 kỳ sản lượng được CĐT xác nhận (giá trị trước thuế).
Workflow 2 bên: Nháp → Đã đề xuất → CĐT duyệt / Huỷ. Chỉ BBNT
'approved' được cộng vào sản lượng lũy kế / khoản phải thu.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class RpOwnerAcceptance(models.Model):
    _name = 'rp.owner.acceptance'
    _description = 'Hồ sơ nghiệm thu với Chủ đầu tư'
    _inherit = ['mail.thread']
    _order = 'date_submitted desc, id desc'

    name = fields.Char(
        string='Số BBNT', required=True, copy=False,
        default=lambda self: _('/'),
        help='Auto sinh OBBNT/YYYY/NNNN khi lưu — sửa được theo số văn '
             'bản thực tế ký với CĐT.')
    contract_id = fields.Many2one(
        'rp.owner.contract', string='HĐ với CĐT', required=True,
        ondelete='cascade', index=True)
    project_id = fields.Many2one(
        related='contract_id.project_id', store=True, index=True)
    owner_id = fields.Many2one(
        related='contract_id.owner_id', store=True,
        string='Chủ đầu tư')
    currency_id = fields.Many2one(
        related='contract_id.currency_id', store=True)
    company_id = fields.Many2one(
        related='contract_id.company_id', store=True)

    date_submitted = fields.Date(
        string='Ngày đề xuất', required=True,
        default=fields.Date.context_today, tracking=True)
    date_approved = fields.Date(
        string='Ngày CĐT duyệt', readonly=True, tracking=True)
    amount_this_period = fields.Monetary(
        string='Giá trị sản lượng kỳ này', required=True, tracking=True,
        help='Giá trị sản lượng (trước thuế) theo biên bản kỳ này. Cho '
             'phép ÂM khi CĐT điều chỉnh giảm sản lượng đã nghiệm thu '
             '(cắt khối lượng sau kiểm toán) — theo biên bản điều chỉnh.')
    state = fields.Selection(
        [('draft', 'Nháp'),
         ('proposed', 'Đã đề xuất'),
         ('approved', 'CĐT duyệt'),
         ('cancelled', 'Huỷ')],
        string='Trạng thái', default='draft', required=True, tracking=True)
    note = fields.Text(string='Ghi chú')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _('/'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'rp.owner.acceptance') or _('/')
        return super().create(vals_list)

    @api.constrains('amount_this_period')
    def _check_amount(self):
        for rec in self:
            if not rec.amount_this_period:
                raise ValidationError(
                    'Giá trị sản lượng kỳ này phải khác 0 '
                    '(âm = điều chỉnh giảm theo biên bản với CĐT).')

    # --- Workflow ---
    def action_propose(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Chỉ BBNT Nháp mới đề xuất được.'))
            rec.state = 'proposed'

    def action_approve(self):
        for rec in self:
            if rec.state != 'proposed':
                raise UserError(_(
                    'Chỉ BBNT Đã đề xuất mới ghi nhận CĐT duyệt được.'))
            # Chặn sản lượng lũy kế vượt giá trị HĐ (cần phụ lục tăng
            # giá trị HĐ trước khi nghiệm thu vượt)
            contract = rec.contract_id
            new_total = rec.amount_this_period + sum(
                contract.acceptance_ids.filtered(
                    lambda a: a.state == 'approved' and a.id != rec.id
                ).mapped('amount_this_period'))
            if new_total > contract.contract_value_pretax + 0.01:
                raise UserError(_(
                    'Sản lượng lũy kế (%(t)s) vượt giá trị HĐ '
                    '(%(v)s). Điều chỉnh giá trị HĐ (phụ lục với CĐT) '
                    'trước khi duyệt BBNT này.',
                    t='{:,.0f}'.format(new_total),
                    v='{:,.0f}'.format(contract.contract_value_pretax)))
            rec.state = 'approved'
            rec.date_approved = fields.Date.context_today(rec)
            rec.message_post(body=_(
                'CĐT duyệt BBNT %(n)s — sản lượng kỳ này %(a)s.',
                n=rec.name,
                a='{:,.0f}'.format(rec.amount_this_period)))

    def action_reset_draft(self):
        for rec in self:
            if rec.state not in ('proposed', 'cancelled'):
                raise UserError(_(
                    'Chỉ reset được BBNT Đã đề xuất hoặc Huỷ.'))
            rec.state = 'draft'

    def action_cancel(self):
        for rec in self:
            if rec.state == 'approved':
                raise UserError(_(
                    'BBNT đã được CĐT duyệt — không huỷ được (ảnh hưởng '
                    'phải thu/TSBĐ). Cần điều chỉnh thì lập BBNT âm kỳ '
                    'sau theo biên bản với CĐT.'))
            rec.state = 'cancelled'
