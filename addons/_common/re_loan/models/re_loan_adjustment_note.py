# -*- coding: utf-8 -*-
"""
Thông báo Nợ / Có — điều chỉnh lãi hồi tố (CC1 #8).

Nghiệp vụ: NH đổi lãi suất qua phụ lục, nhưng khách đã thanh toán kỳ
lãi TRƯỚC khi phụ lục có hiệu lực → chênh lệch giữa số đã trả (LS cũ)
và số đúng (LS mới hồi tố). NH tính chênh lệch và phát hành:
  - Thông báo NỢ  (truy thu):  khách phải trả THÊM  → tăng kỳ áp dụng
  - Thông báo CÓ  (truy hoàn): khách được giảm trừ  → giảm kỳ áp dụng

App KHÔNG recompute hồi tố — số tiền là INPUT từ thông báo NH. Kỳ đã
thanh toán không bị sửa (audit trail + khớp sổ phụ NH). Apply tạo 1
dòng lịch lãi loại "Điều chỉnh" vào kỳ chưa thanh toán (mặc định kỳ
hiện tại).
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ReLoanAdjustmentNote(models.Model):
    _name = 're.loan.adjustment.note'
    _description = 'Thông báo Nợ/Có (điều chỉnh lãi)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_issue desc, id desc'

    name = fields.Char(
        string='Số thông báo', required=True, copy=False, tracking=True,
        default=lambda self: _('Mới'),
        help='Số thông báo do NH phát hành (nhập theo chứng từ NH), '
             'hoặc để "Mới" để hệ thống tự sinh.')
    kind = fields.Selection(
        [('debit',  'Thông báo Nợ (truy thu — khách trả thêm)'),
         ('credit', 'Thông báo Có (truy hoàn — giảm trừ)')],
        string='Loại', required=True, default='debit', tracking=True,
        help='Nghiệp vụ NH VN: thông báo NỢ = NH ghi Nợ TK khách '
             '(trừ tiền / khách phải trả thêm); thông báo CÓ = NH ghi '
             'Có TK khách (cộng tiền / giảm trừ kỳ tới).')
    note_id = fields.Many2one(
        're.loan.note', string='Khế ước', required=True, tracking=True,
        domain="[('state', 'in', ('active', 'partial_paid'))]")
    partner_id = fields.Many2one(
        related='note_id.partner_id', string='Ngân hàng', store=True)
    currency_id = fields.Many2one(
        related='note_id.currency_id', store=True, readonly=True)
    company_id = fields.Many2one(
        related='note_id.company_id', store=True, readonly=True)

    amount = fields.Monetary(
        string='Số tiền', required=True, tracking=True,
        help='Số tiền chênh lệch trên thông báo NH (luôn nhập số dương; '
             'loại Nợ/Có quyết định tăng hay giảm).')
    date_issue = fields.Date(
        string='Ngày phát hành', required=True,
        default=fields.Date.context_today, tracking=True)
    target_interest_line_id = fields.Many2one(
        're.loan.note.interest.line', string='Kỳ áp dụng',
        domain="[('note_id', '=', note_id), ('state', 'in', ('planned', 'accrued', 'partial_paid')), ('line_type', '=', 'period')]",
        compute='_compute_target_line', store=True, readonly=False,
        tracking=True,
        help='Kỳ lịch lãi CHƯA thanh toán mà chênh lệch sẽ cộng/trừ '
             'vào. Mặc định = kỳ hiện tại (kỳ chưa trả gần nhất).')
    reason = fields.Text(
        string='Lý do / diễn giải',
        help='VD: Điều chỉnh lãi kỳ 2-3 do thay đổi lãi suất '
             '12.5% → 13% hiệu lực hồi tố 01/03/2026 theo PL số 03.')

    adjustment_line_id = fields.Many2one(
        're.loan.note.interest.line', string='Dòng điều chỉnh',
        readonly=True, copy=False,
        help='Dòng lịch lãi loại "Điều chỉnh" được tạo khi apply.')

    state = fields.Selection(
        [('draft',     'Nháp'),
         ('applied',   'Đã áp dụng'),
         ('cancelled', 'Đã huỷ')],
        string='Trạng thái', default='draft', required=True, tracking=True)

    # ------------------------------------------------------------------
    @api.depends('note_id')
    def _compute_target_line(self):
        """Default kỳ áp dụng = kỳ chưa thanh toán sớm nhất (kỳ hiện tại)."""
        for rec in self:
            if rec.target_interest_line_id and \
                    rec.target_interest_line_id.note_id == rec.note_id:
                continue
            rec.target_interest_line_id = self.env[
                're.loan.note.interest.line'].search([
                    ('note_id', '=', rec.note_id.id),
                    ('state', 'in', ('planned', 'accrued', 'partial_paid')),
                    ('line_type', '=', 'period'),
                ], order='period_no', limit=1)

    @api.constrains('amount')
    def _check_amount(self):
        for rec in self:
            if rec.amount <= 0:
                raise UserError(_(
                    "Số tiền thông báo phải > 0. Loại Nợ/Có quyết định "
                    "tăng hay giảm — không nhập số âm."))

    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _('Mới'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    're.loan.adjustment.note') or _('Mới')
        return super().create(vals_list)

    # ------------------------------------------------------------------
    def action_apply(self):
        """Tạo dòng lịch lãi 'Điều chỉnh' vào kỳ áp dụng."""
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_("Chỉ thông báo Nháp mới áp dụng được."))
            line = rec.target_interest_line_id
            if not line:
                raise UserError(_(
                    "Chưa chọn Kỳ áp dụng — KW này không còn kỳ nào "
                    "chưa thanh toán."))
            if line.state == 'paid':
                raise UserError(_(
                    "Kỳ áp dụng đã thanh toán đủ — chọn kỳ khác."))
            sign = 1 if rec.kind == 'debit' else -1
            adj = self.env['re.loan.note.interest.line'].create({
                'note_id': rec.note_id.id,
                'line_type': 'adjustment',
                'adjustment_note_id': rec.id,
                'period_no': line.period_no,
                'date_from': line.date_from,
                'date_to': line.date_to,
                'principal_base': 0,
                'interest_rate': 0,
                'is_overridden': True,
                'interest_amount_manual': sign * rec.amount,
                'state': 'planned',
            })
            rec.adjustment_line_id = adj
            rec.state = 'applied'
            rec.message_post(body=_(
                "Đã áp dụng vào Kỳ %(period)s — %(dir)s %(amt)s.",
                period=line.period_no,
                dir=_('truy thu (+)') if sign > 0 else _('truy hoàn (−)'),
                amt=f'{rec.amount:,.0f} {rec.currency_id.symbol or "đ"}'))
        return True

    def action_cancel(self):
        """Huỷ thông báo — gỡ dòng điều chỉnh nếu kỳ chưa bị trả."""
        for rec in self:
            if rec.state == 'applied' and rec.adjustment_line_id:
                if rec.adjustment_line_id.amount_paid_total:
                    raise UserError(_(
                        "Dòng điều chỉnh đã có tiền trả allocate — không "
                        "huỷ được. Đối chiếu với NH trước."))
                rec.adjustment_line_id.unlink()
            rec.state = 'cancelled'

    def action_reset_draft(self):
        for rec in self:
            if rec.state != 'cancelled':
                raise UserError(_("Chỉ thông báo Đã huỷ mới về Nháp được."))
            rec.state = 'draft'

    def unlink(self):
        if any(rec.state == 'applied' for rec in self):
            raise UserError(_(
                "Không xoá thông báo Đã áp dụng — huỷ trước để gỡ dòng "
                "điều chỉnh (giữ vết audit)."))
        return super().unlink()
