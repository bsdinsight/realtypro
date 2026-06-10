# -*- coding: utf-8 -*-
"""
Phụ lục khế ước (amendment) — văn bản sửa đổi một KW.

6 loại: gia hạn, đổi số tiền, đổi lãi suất, đổi mục đích, đổi lịch trả gốc,
đổi tài sản thế chấp. Khi áp dụng, ghi giá trị cũ (audit) và ghi giá trị mới
vào KW; với thay đổi trọng yếu (số tiền/lãi suất/kỳ hạn/lịch trả) sẽ sinh lại
lịch lãi dự kiến.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class ReLoanNoteAmendment(models.Model):
    _name = 're.loan.note.amendment'
    _description = 'Phụ lục khế ước'
    _inherit = ['mail.thread']
    _order = 'date_effective desc, id desc'

    name = fields.Char(
        string='Số phụ lục', required=True, copy=False,
        help='Số phụ lục NH cấp (nhập tay).')
    note_id = fields.Many2one(
        're.loan.note', string='Khế ước', required=True, ondelete='cascade',
        tracking=True)
    amendment_type = fields.Selection(
        [('extension', 'Gia hạn'),
         ('amount', 'Đổi số tiền'),
         ('rate', 'Đổi lãi suất'),
         ('purpose', 'Đổi mục đích'),
         ('schedule', 'Đổi lịch trả gốc'),
         ('collateral', 'Đổi tài sản thế chấp')],
        string='Loại phụ lục', required=True, tracking=True)
    date_effective = fields.Date(
        string='Ngày hiệu lực', required=True,
        default=fields.Date.context_today)

    # Giá trị mới theo loại (hiển thị có điều kiện trên form)
    new_date_maturity = fields.Date(string='Ngày đáo hạn mới')
    new_amount = fields.Monetary(string='Số tiền mới')
    new_interest_rate = fields.Float(string='Lãi suất mới (%/năm)',
                                     digits=(5, 2))
    new_purpose = fields.Text(string='Mục đích mới')
    new_repayment_plan = fields.Selection(
        [('bullet', 'Trả gốc cuối kỳ (Bullet)'),
         ('equal_principal', 'Trả gốc đều'),
         ('custom', 'Tuỳ chỉnh')],
        string='Lịch trả gốc mới')
    description = fields.Text(string='Diễn giải')

    # Audit
    value_old = fields.Char(string='Giá trị cũ', readonly=True)
    value_new = fields.Char(string='Giá trị mới', readonly=True)

    state = fields.Selection(
        [('draft', 'Nháp'), ('applied', 'Đã áp dụng')],
        string='Trạng thái', default='draft', required=True, tracking=True)

    currency_id = fields.Many2one(
        related='note_id.currency_id', store=True, readonly=True)
    company_id = fields.Many2one(
        related='note_id.company_id', store=True, readonly=True)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    @api.constrains('amendment_type', 'new_amount', 'new_interest_rate')
    def _check_new_values(self):
        for am in self:
            if am.amendment_type == 'amount' and am.new_amount <= 0:
                raise ValidationError(_("Số tiền mới phải lớn hơn 0."))
            if am.amendment_type == 'rate' and am.new_interest_rate < 0:
                raise ValidationError(_("Lãi suất mới không được âm."))

    # ------------------------------------------------------------------
    # Apply
    # ------------------------------------------------------------------
    def action_apply(self):
        for am in self:
            if am.state != 'draft':
                raise UserError(_("Phụ lục này đã được áp dụng."))
            note = am.note_id
            if note.state in ('draft', 'cancelled'):
                raise UserError(_(
                    "Chỉ áp dụng phụ lục cho KW đã Hiệu lực."))
            t = am.amendment_type
            material = False
            if t == 'extension':
                if not am.new_date_maturity:
                    raise UserError(_("Cần nhập Ngày đáo hạn mới."))
                am.value_old = str(note.date_maturity or '')
                am.value_new = str(am.new_date_maturity)
                note.date_maturity = am.new_date_maturity
                material = True
            elif t == 'amount':
                am.value_old = '{:,.0f}'.format(note.amount)
                am.value_new = '{:,.0f}'.format(am.new_amount)
                note.amount = am.new_amount
                material = True
            elif t == 'rate':
                # value_old = rate hiệu lực TRƯỚC phụ lục này (= rate
                # phụ lục cuối cùng đã apply trước rec, hoặc rate ký
                # ban đầu nếu chưa có phụ lục nào). Dùng
                # _effective_rate_at(date_effective − 1 ngày) để đúng.
                from datetime import timedelta as _td
                rate_before = note._effective_rate_at(
                    am.date_effective - _td(days=1))
                am.value_old = '{:.2f}'.format(rate_before)
                am.value_new = '{:.2f}'.format(am.new_interest_rate)
                # KHÔNG overwrite note.interest_rate — đó là rate ký
                # ban đầu, phải giữ immutable. Lịch sử rate xem qua
                # amendment_ids.
                # Lãi mới áp dụng cho các kỳ planned có
                # date_from >= date_effective.
                future = note.interest_line_ids.filtered(
                    lambda l: l.state == 'planned'
                    and l.date_from and l.date_from >= am.date_effective)
                future.write({'interest_rate': am.new_interest_rate})
                # KHÔNG regen toàn bộ. material vẫn = False.
            elif t == 'purpose':
                am.value_old = (note.purpose or '')[:200]
                am.value_new = (am.new_purpose or '')[:200]
                note.purpose = am.new_purpose
            elif t == 'schedule':
                if not am.new_repayment_plan:
                    raise UserError(_("Cần chọn Lịch trả gốc mới."))
                am.value_old = note.repayment_plan or ''
                am.value_new = am.new_repayment_plan
                note.repayment_plan = am.new_repayment_plan
                material = True
            elif t == 'collateral':
                # L3: chỉ ghi nhận diễn giải; thay đổi pledge xử lý ở L3.
                am.value_old = ''
                am.value_new = (am.description or '')[:200]
            am.state = 'applied'
            note.message_post(body=_(
                "Áp dụng phụ lục %(name)s (%(type)s): %(old)s → %(new)s",
                name=am.name,
                type=dict(self._fields['amendment_type'].selection).get(t),
                old=am.value_old or '—', new=am.value_new or '—'))
            # Sinh lại lịch lãi với thay đổi trọng yếu.
            if material and note.state in ('active', 'partial_paid', 'overdue'):
                note.action_generate_interest_schedule()
        # Force reload form để các tab parent (Lịch lãi, Phụ lục) refresh
        # ngay; không cần F5.
        return {'type': 'ir.actions.client', 'tag': 'soft_reload'}

    def unlink(self):
        for am in self:
            if am.state == 'applied':
                raise UserError(_(
                    "Không thể xoá phụ lục đã áp dụng (giữ vết). "
                    "Tạo phụ lục mới để điều chỉnh."))
        return super().unlink()
