# -*- coding: utf-8 -*-
"""Chấm dứt / Thanh lý HĐ nhà thầu.

Hai văn bản khép vòng đời HĐ, cùng cấu trúc hồ sơ nên chung 1 model:

- **Chấm dứt** (termination): dừng HĐ sớm khi đang ký/thi công —
  ghi căn cứ, giá trị đã thực hiện tới thời điểm dừng.
- **Thanh lý** (liquidation): biên bản thanh lý sau khi HĐ hoàn thành
  hoặc chấm dứt — quyết toán giá trị cuối, đối chiếu đã thanh toán,
  xác nhận các bên hết nghĩa vụ.

Xác nhận văn bản sẽ chuyển state HĐ tương ứng (terminated / liquidated).
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class RpContractClosure(models.Model):
    _name = 'rp.contract.closure'
    _description = 'Chấm dứt / Thanh lý HĐ nhà thầu'
    _inherit = ['mail.thread']
    _order = 'date desc, id desc'

    name = fields.Char(
        string='Số văn bản', required=True, copy=False, tracking=True,
        help='Số biên bản chấm dứt / biên bản thanh lý HĐ.')
    closure_type = fields.Selection(
        [('termination', 'Chấm dứt HĐ'),
         ('liquidation', 'Thanh lý HĐ')],
        string='Loại', required=True, default='liquidation', tracking=True)
    contract_id = fields.Many2one(
        'rp.contract', string='HĐ', required=True, ondelete='restrict',
        index=True, tracking=True)
    project_id = fields.Many2one(
        related='contract_id.project_id', store=True, readonly=True)
    contractor_id = fields.Many2one(
        related='contract_id.contractor_id', store=True, readonly=True,
        string='Nhà thầu')
    date = fields.Date(
        string='Ngày văn bản', required=True,
        default=fields.Date.context_today, tracking=True)
    reason = fields.Text(
        string='Căn cứ / lý do', required=True,
        help='Chấm dứt: lý do dừng (vi phạm, bất khả kháng, thoả thuận...). '
             'Thanh lý: căn cứ nghiệm thu hoàn thành, biên bản liên quan.')

    # ----- Quyết toán
    value_executed = fields.Monetary(
        string='Giá trị đã thực hiện', tracking=True,
        help='Giá trị khối lượng đã thực hiện được 2 bên xác nhận '
             '(quyết toán). Gợi ý từ nghiệm thu lũy kế nếu có.')
    value_paid = fields.Monetary(
        string='Đã thanh toán', tracking=True,
        help='Tổng đã thanh toán theo mốc (gợi ý từ lịch thanh toán).')
    value_remaining = fields.Monetary(
        string='Còn phải trả', compute='_compute_value_remaining',
        store=True,
        help='= Giá trị đã thực hiện − Đã thanh toán. '
             'Âm nghĩa là phải thu hồi (đã trả thừa/tạm ứng chưa cấn trừ).')

    state = fields.Selection(
        [('draft', 'Nháp'),
         ('confirmed', 'Đã xác nhận'),
         ('cancelled', 'Huỷ')],
        string='Trạng thái', default='draft', required=True, tracking=True,
        copy=False)

    currency_id = fields.Many2one(
        related='contract_id.currency_id', store=True, readonly=True)
    company_id = fields.Many2one(
        related='contract_id.company_id', store=True, readonly=True)

    @api.depends('value_executed', 'value_paid')
    def _compute_value_remaining(self):
        for rec in self:
            rec.value_remaining = rec.value_executed - rec.value_paid

    @api.onchange('contract_id')
    def _onchange_contract_id(self):
        for rec in self:
            if not rec.contract_id:
                continue
            # acceptance_value_to_date do rp_progress thêm vào rp.contract —
            # core không depends rp_progress nên đọc mềm qua getattr.
            rec.value_executed = getattr(
                rec.contract_id, 'acceptance_value_to_date', 0.0) or 0.0
            rec.value_paid = sum(
                rec.contract_id.payment_milestone_ids
                .filtered(lambda m: m.state == 'paid').mapped('amount'))

    @api.constrains('closure_type', 'contract_id', 'state')
    def _check_contract_state(self):
        for rec in self:
            if rec.state != 'draft':
                continue
            cst = rec.contract_id.state
            if rec.closure_type == 'termination' \
                    and cst not in ('signed', 'executing'):
                raise ValidationError(
                    'Chỉ chấm dứt được HĐ đang ở trạng thái '
                    'Đã ký / Đang thực hiện.')
            if rec.closure_type == 'liquidation' \
                    and cst not in ('completed', 'terminated'):
                raise ValidationError(
                    'Chỉ thanh lý được HĐ đã Hoàn thành hoặc Đã chấm dứt.')

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------
    def action_confirm(self):
        for rec in self:
            if rec.state != 'draft':
                continue
            if rec.closure_type == 'termination':
                rec.contract_id.state = 'terminated'
            else:
                rec.contract_id.state = 'liquidated'
            rec.state = 'confirmed'
            rec.contract_id.message_post(body=_(
                '%(type)s theo văn bản %(name)s ngày %(date)s — '
                'giá trị thực hiện %(exe)s, đã thanh toán %(paid)s.',
                type=dict(rec._fields['closure_type'].selection)
                    .get(rec.closure_type),
                name=rec.name, date=rec.date,
                exe=f'{rec.value_executed:,.0f}',
                paid=f'{rec.value_paid:,.0f}'))
        return True

    def action_cancel(self):
        for rec in self:
            if rec.state == 'confirmed':
                raise UserError(
                    'Văn bản đã xác nhận — dùng "Về Nháp" trên HĐ nếu '
                    'thật sự cần đảo (manager).')
            rec.state = 'cancelled'
        return True

    def action_reset_draft(self):
        for rec in self:
            if rec.state == 'cancelled':
                rec.state = 'draft'
        return True
