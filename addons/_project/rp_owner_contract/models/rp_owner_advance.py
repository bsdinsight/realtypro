# -*- coding: utf-8 -*-
"""Tạm ứng CỦA CHỦ ĐẦU TƯ — tiền CĐT ứng trước cho mình (vai tổng thầu).

Anh Đại 2026-08-10. Phân biệt rõ với `rp_advance_payment` (module đó là
tạm ứng mình CHI cho thầu phụ / nhà cung cấp — chiều ngược lại).

Trước đây tạm ứng CĐT chỉ là MỘT Ô SỐ trên hợp đồng (`advance_amount`),
không có chứng từ, không biết nhận mấy đợt, ngày nào, bảo lãnh tạm ứng
ra sao. Nay mỗi đợt là một bản ghi; `advance_amount` trên hợp đồng đổi
thành TỔNG các đợt đã nhận (một nguồn sự thật duy nhất).

Thu hồi: vẫn khấu trừ dần qua BBNT (`acceptance.advance_recovery`) như
cũ — số thu hồi của hợp đồng được phân bổ về từng đợt theo **FIFO**
(đợt nhận trước thu hồi trước), nên mỗi đợt biết còn dư bao nhiêu.

Số dư tạm ứng là đầu vào ③ của phiếu Nhu cầu vốn dự án (tài liệu nghiệp vụ §3:
"trừ đi phần đã có nguồn — tạm ứng còn dùng được").
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class RpOwnerAdvance(models.Model):
    _name = 'rp.owner.advance'
    _description = 'Tạm ứng của Chủ đầu tư'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_received desc, date_request desc, id desc'

    name = fields.Char(
        string='Số phiếu', required=True, copy=False, default='/',
        tracking=True)
    owner_contract_id = fields.Many2one(
        'rp.owner.contract', string='HĐ với CĐT', required=True,
        ondelete='restrict', index=True, tracking=True)
    project_id = fields.Many2one(
        related='owner_contract_id.project_id', string='Dự án',
        store=True, readonly=True)
    owner_id = fields.Many2one(
        related='owner_contract_id.owner_id', string='Chủ đầu tư',
        store=True, readonly=True)
    currency_id = fields.Many2one(
        related='owner_contract_id.currency_id', store=True, readonly=True)

    date_request = fields.Date(
        string='Ngày đề nghị', default=fields.Date.context_today,
        tracking=True)
    date_received = fields.Date(string='Ngày nhận tiền', tracking=True)
    amount = fields.Monetary(
        string='Số tiền tạm ứng', required=True, tracking=True)
    percent_of_contract = fields.Float(
        string='% giá trị HĐ', compute='_compute_percent',
        help='Tạm ứng thường 10–20% giá trị hợp đồng.')
    recovery_percent = fields.Float(
        string='% thu hồi mỗi kỳ', tracking=True,
        help='Tỷ lệ khấu trừ trên sản lượng mỗi kỳ để thu hồi đợt tạm '
             'ứng này. Mặc định lấy theo hợp đồng.')

    # --- Bảo lãnh tạm ứng (CĐT hầu như luôn đòi) ---
    guarantee_required = fields.Boolean(
        string='Có bảo lãnh tạm ứng', default=True, tracking=True)
    guarantee_ref = fields.Char(string='Số chứng thư BL')
    guarantee_bank_id = fields.Many2one(
        'res.partner', string='NH phát hành BL',
        domain="[('is_company', '=', True)]")
    guarantee_date_expiry = fields.Date(string='BL hết hạn')

    state = fields.Selection(
        [('draft', 'Nháp'),
         ('requested', 'Đã đề nghị CĐT'),
         ('received', 'Đã nhận tiền'),
         ('closed', 'Đã thu hồi hết'),
         ('cancelled', 'Huỷ')],
        string='Trạng thái', default='draft', required=True, tracking=True)

    amount_recovered = fields.Monetary(
        string='Đã thu hồi', compute='_compute_recovery', store=True,
        help='Phần đã khấu trừ qua các BBNT đã duyệt — phân bổ theo FIFO '
             'giữa các đợt tạm ứng của cùng hợp đồng.')
    amount_remaining = fields.Monetary(
        string='Còn phải thu hồi', compute='_compute_recovery', store=True,
        help='MẶT NỢ: còn phải hoàn lại CĐT (bị khấu trừ dần qua BBNT).')
    amount_used_payment = fields.Monetary(
        string='Đã dùng trả nhà thầu/NCC', compute='_compute_cash',
        help='Σ các mốc thanh toán HĐ nhà thầu chọn nguồn = đợt tạm ứng '
             'này. Tiền đã ra khỏi tài khoản.')
    amount_cash_left = fields.Monetary(
        string='Còn trong tài khoản', compute='_compute_cash',
        help='MẶT TIỀN: = Số tiền tạm ứng − Đã dùng trả nhà thầu/NCC. '
             'Đây mới là "tạm ứng CÒN DÙNG ĐƯỢC" của tài liệu nghiệp vụ §3 — '
             'khác với "Còn phải thu hồi" (mặt nợ với CĐT).')

    def _compute_cash(self):
        Ms = self.env['rp.contract.payment.milestone']
        has = 'owner_advance_id' in Ms._fields
        for rec in self:
            used = 0.0
            if has and rec.id:
                # mốc khai 1 nguồn + mốc chia nhiều nguồn, gộp qua helper
                cands = Ms.search([
                    '|', ('owner_advance_id', '=', rec.id),
                    ('funding_line_ids.owner_advance_id', '=', rec.id)])
                used = sum(m._amount_from_source('owner_advance', rec)
                           for m in cands)
            rec.amount_used_payment = used
            rec.amount_cash_left = max(0.0, (rec.amount or 0.0) - used)
    note = fields.Text(string='Ghi chú')

    @api.depends('amount', 'owner_contract_id.contract_value_total')
    def _compute_percent(self):
        for rec in self:
            total = rec.owner_contract_id.contract_value_total or 0.0
            rec.percent_of_contract = (
                (rec.amount or 0.0) / total * 100.0) if total else 0.0

    @api.depends('amount', 'state', 'date_received',
                 'owner_contract_id.acceptance_ids.advance_recovery',
                 'owner_contract_id.acceptance_ids.state')
    def _compute_recovery(self):
        """Phân bổ FIFO tổng thu hồi của HĐ về từng đợt tạm ứng."""
        for contract in self.mapped('owner_contract_id'):
            approved = contract.acceptance_ids.filtered(
                lambda a: a.state == 'approved')
            pool = sum(approved.mapped('advance_recovery'))
            advances = self.search([
                ('owner_contract_id', '=', contract.id),
                ('state', 'not in', ('cancelled', 'draft'))],
                order='date_received asc, date_request asc, id asc')
            for adv in advances:
                take = min(pool, adv.amount or 0.0)
                pool -= take
                if adv in self:
                    adv.amount_recovered = take
                    adv.amount_remaining = max(0.0, (adv.amount or 0.0) - take)
        # đợt nháp/huỷ không tham gia thu hồi
        for rec in self:
            if rec.state in ('draft', 'cancelled'):
                rec.amount_recovered = 0.0
                rec.amount_remaining = rec.amount or 0.0

    @api.onchange('owner_contract_id')
    def _onchange_contract_defaults(self):
        if self.owner_contract_id and not self.recovery_percent:
            self.recovery_percent = \
                self.owner_contract_id.advance_recovery_percent

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'rp.owner.advance') or '/'
        return super().create(vals_list)

    @api.constrains('amount')
    def _check_amount(self):
        for rec in self:
            if rec.amount <= 0:
                raise ValidationError(_('Số tiền tạm ứng phải lớn hơn 0.'))

    @api.constrains('amount', 'owner_contract_id', 'state')
    def _check_total_within_contract(self):
        """Σ tạm ứng không vượt giá trị hợp đồng — khai nhầm số 0 là lộ."""
        for rec in self:
            ct = rec.owner_contract_id
            if not ct or not ct.contract_value_total:
                continue
            total = sum(self.search([
                ('owner_contract_id', '=', ct.id),
                ('state', 'not in', ('cancelled',))]).mapped('amount'))
            if total > ct.contract_value_total:
                raise ValidationError(_(
                    "Σ tạm ứng (%(t)s) vượt giá trị HĐ %(c)s (%(v)s).",
                    t='{:,.0f}'.format(total), c=ct.name,
                    v='{:,.0f}'.format(ct.contract_value_total)))

    # ── Vòng đời ──
    def action_request(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Chỉ đề nghị được từ trạng thái Nháp.'))
            rec.state = 'requested'

    def action_receive(self):
        for rec in self:
            if rec.state not in ('draft', 'requested'):
                raise UserError(_('Chỉ ghi nhận tiền về từ Nháp / Đã đề nghị.'))
            if rec.guarantee_required and not rec.guarantee_ref:
                raise UserError(_(
                    "Đợt tạm ứng %s yêu cầu bảo lãnh tạm ứng — nhập Số "
                    "chứng thư BL trước khi ghi nhận tiền về (CĐT không "
                    "giải ngân tạm ứng khi chưa có BL).", rec.name))
            rec.date_received = rec.date_received or fields.Date.context_today(rec)
            rec.state = 'received'
            rec.message_post(body=_(
                'Đã nhận tạm ứng %(a)s từ CĐT %(o)s.',
                a='{:,.0f}'.format(rec.amount),
                o=rec.owner_id.display_name or ''))

    def action_cancel(self):
        for rec in self:
            if rec.amount_recovered > 0:
                raise UserError(_(
                    'Đợt %s đã thu hồi một phần — không huỷ được.', rec.name))
            rec.state = 'cancelled'

    def action_draft(self):
        self.write({'state': 'draft'})


class RpOwnerContractAdvance(models.Model):
    _inherit = 'rp.owner.contract'

    advance_ids = fields.One2many(
        'rp.owner.advance', 'owner_contract_id', string='Đợt tạm ứng')
    advance_count = fields.Integer(compute='_compute_advance_count')

    def _compute_advance_count(self):
        for rec in self:
            rec.advance_count = len(rec.advance_ids)

    def action_open_advances(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Tạm ứng CĐT — %s') % self.name,
            'res_model': 'rp.owner.advance',
            'view_mode': 'list,form',
            'domain': [('owner_contract_id', '=', self.id)],
            'context': {'default_owner_contract_id': self.id},
        }
