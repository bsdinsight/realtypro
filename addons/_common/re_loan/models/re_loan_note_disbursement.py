# -*- coding: utf-8 -*-
"""Giải ngân (disbursement) — một lần ngân hàng chuyển tiền theo một KW.

Workflow (chuẩn NH VN — chuyển trực tiếp về nhà thầu, không qua TK CC1):
  draft → submitted → approved → disbursed
                   ↘ cancelled

- draft: nhập tay, đính kèm hồ sơ (BBN + hóa đơn) — qua rp_loan_bridge
- submitted: gửi hồ sơ lên NH chờ duyệt
- approved: NH duyệt giải ngân
- disbursed: NH đã chuyển tiền vào tài khoản NT

Beneficiary = nhà thầu nhận tiền (không phải CC1) + TK NH của NT.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class ReLoanNoteDisbursement(models.Model):
    _name = 're.loan.note.disbursement'
    _description = 'Giải ngân khế ước'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date, id'

    name = fields.Char(
        string='Số chứng từ giải ngân', copy=False,
        help='Auto sinh sequence GN/YYYY/NNNNN khi save lần đầu.')
    note_id = fields.Many2one(
        're.loan.note', string='Khế ước', required=True, ondelete='cascade',
        tracking=True)
    date = fields.Date(
        string='Ngày giải ngân', required=True, tracking=True,
        default=fields.Date.context_today)
    amount = fields.Monetary(string='Số tiền', required=True, tracking=True)
    reference = fields.Char(string='Chứng từ NH')
    description = fields.Char(
        string='Diễn giải',
        help='Vd "Trả nhà thầu A đợt 1", "Mua thiết bị...".')

    # --- Bên thụ hưởng: nhà thầu nhận tiền ---
    beneficiary_partner_id = fields.Many2one(
        'res.partner', string='Bên nhận tiền (Nhà thầu)',
        tracking=True,
        help='Bên thực nhận giải ngân — chuẩn NH VN chuyển trực tiếp '
             'cho nhà thầu, KHÔNG qua tài khoản CC1.')
    beneficiary_bank_account_id = fields.Many2one(
        'res.partner.bank', string='Tài khoản NH của Nhà thầu',
        tracking=True,
        domain="[('partner_id', '=', beneficiary_partner_id)]",
        help='Số TK NH của nhà thầu nhận tiền. Chỉ hiện TK gắn với '
             'partner đã chọn ở trên.')

    state = fields.Selection(
        [('draft', 'Nháp'),
         ('submitted', 'Đã gửi NH'),
         ('approved', 'NH duyệt'),
         ('disbursed', 'Đã giải ngân'),
         ('cancelled', 'Huỷ')],
        string='Trạng thái', default='draft', required=True, tracking=True)

    # ------------------------------------------------------------------
    # Onchange: auto-fill TK NH theo Bên nhận tiền
    # ------------------------------------------------------------------
    @api.onchange('beneficiary_partner_id')
    def _onchange_beneficiary_autofill_bank(self):
        """Khi chọn nhà thầu, auto-pick TK NH đầu tiên của họ.
        User vẫn sửa được nếu cần chọn TK khác.
        """
        if self.beneficiary_partner_id:
            banks = self.beneficiary_partner_id.bank_ids
            # Auto-pick TK đầu tiên (thường là TK chính NT đăng ký)
            self.beneficiary_bank_account_id = banks[:1] if banks else False
        else:
            self.beneficiary_bank_account_id = False

    # --- Ngày NH duyệt thực tế (start tính lãi từ đây) ---
    date_bank_approved = fields.Date(
        string='Ngày NH duyệt giải ngân', tracking=True,
        help='Ngày NH ký duyệt chuyển tiền (ngoài hệ thống). User '
             'nhập khi đánh dấu Đã giải ngân. Lịch lãi của KW sẽ '
             'tính lại bắt đầu từ ngày này.')
    allowed_project_ids = fields.Many2many(
        're.project', string='Dự án cho phép',
        compute='_compute_allowed_project_ids',
        help='Dự án cho phép chọn (CC1 #6):\n'
             '- Nếu facility CÓ phân bổ dự án → chỉ các dự án trong '
             'phân bổ đó.\n'
             '- Nếu facility KHÔNG có phân bổ → TẤT CẢ dự án.')
    project_id = fields.Many2one(
        're.project', string='Dự án',
        domain="[('id', 'in', allowed_project_ids)]",
        help='Dự án thực chi từ khoản giải ngân này. Filter theo CC1 '
             '#6: chỉ dự án phân bổ trên facility, hoặc tất cả nếu '
             'facility chưa phân bổ.')
    currency_id = fields.Many2one(
        related='note_id.currency_id', store=True, readonly=True)
    company_id = fields.Many2one(
        related='note_id.company_id', store=True, readonly=True)

    @api.depends('note_id.facility_id.project_allocation_ids.project_id')
    def _compute_allowed_project_ids(self):
        Project = self.env['re.project']
        all_projects = Project.search([])
        for rec in self:
            facility = rec.note_id.facility_id
            if facility and facility.project_allocation_ids:
                # CÓ phân bổ → chỉ các dự án trong phân bổ
                rec.allowed_project_ids = facility.project_allocation_ids \
                    .mapped('project_id')
            else:
                # KHÔNG phân bổ (hoặc chưa pick facility) → tất cả dự án
                rec.allowed_project_ids = all_projects

    @api.constrains('amount', 'note_id')
    def _check_amount(self):
        for rec in self:
            if rec.amount <= 0:
                raise ValidationError(_("Số tiền giải ngân phải lớn hơn 0."))
            note = rec.note_id
            total = sum(note.disbursement_ids.mapped('amount'))
            if total > note.amount:
                raise ValidationError(_(
                    "Tổng giải ngân (%(t)s) vượt số tiền KW '%(n)s' (%(a)s).",
                    t=total, n=note.name, a=note.amount))

    # ------------------------------------------------------------------
    # Cập nhật lifecycle KW sau khi giải ngân thay đổi
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals.get('name') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    're.loan.note.disbursement') or '/'
        recs = super().create(vals_list)
        recs.note_id._update_payment_state()
        return recs

    def write(self, vals):
        res = super().write(vals)
        self.note_id._update_payment_state()
        return res

    def unlink(self):
        for rec in self:
            if rec.state == 'disbursed':
                raise UserError(_(
                    "Không thể xoá giải ngân đã giải ngân (state='disbursed'). "
                    "Huỷ thay vì xoá để giữ vết."))
        notes = self.note_id
        res = super().unlink()
        notes._update_payment_state()
        return res

    # ------------------------------------------------------------------
    # State machine — workflow giải ngân
    # ------------------------------------------------------------------
    def _check_ready_to_submit(self):
        """Kiểm tra trước khi gửi NH duyệt. Phase 1: chỉ check beneficiary.
        Phase 2 (rp_loan_bridge): override để check dossier (BBN + hóa đơn).
        """
        for rec in self:
            if not rec.beneficiary_partner_id:
                raise UserError(_(
                    "Cần điền 'Bên nhận tiền (Nhà thầu)' trước khi gửi NH."))
            if not rec.beneficiary_bank_account_id:
                raise UserError(_(
                    "Cần điền 'Tài khoản NH của Nhà thầu' — chuẩn NH VN "
                    "chuyển trực tiếp cho nhà thầu, không qua TK CC1."))

    def action_submit(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_(
                    "Chỉ giải ngân ở trạng thái Nháp mới gửi NH được."))
            rec._check_ready_to_submit()
            rec.state = 'submitted'
            rec.message_post(body=_(
                "Đã gửi hồ sơ giải ngân lên NH — chờ duyệt."))

    def action_approve(self):
        for rec in self:
            if rec.state != 'submitted':
                raise UserError(_(
                    "Chỉ giải ngân Đã gửi NH mới duyệt được."))
            rec.state = 'approved'
            rec.message_post(body=_("NH duyệt giải ngân."))

    def action_disburse(self):
        for rec in self:
            if rec.state != 'approved':
                raise UserError(_(
                    "Chỉ giải ngân đã được NH duyệt mới chuyển tiền được."))
            if not rec.date_bank_approved:
                raise UserError(_(
                    "Cần nhập 'Ngày NH duyệt giải ngân' trước khi đánh "
                    "dấu Đã giải ngân — lịch lãi của KW sẽ tính từ "
                    "ngày này."))
            rec.state = 'disbursed'
            # Cập nhật date_note của KW = max ngày NH duyệt sớm nhất
            # của các giải ngân (nếu chưa được set hoặc earlier).
            note = rec.note_id
            if note and (not note.date_note
                         or rec.date_bank_approved < note.date_note):
                note.date_note = rec.date_bank_approved
                # Regen lịch lãi từ ngày mới
                if note.state in ('active', 'partial_paid'):
                    note.action_generate_interest_schedule()
                rec.message_post(body=_(
                    "Cập nhật date_note của KW = %(d)s + regen lịch lãi.",
                    d=rec.date_bank_approved))
            rec.message_post(body=_(
                "NH đã chuyển %(a)s vào TK %(tk)s của %(p)s ngày %(d)s.",
                a=rec.amount,
                tk=rec.beneficiary_bank_account_id.acc_number or '',
                p=rec.beneficiary_partner_id.name or '',
                d=rec.date_bank_approved))

    def action_reset_draft(self):
        for rec in self:
            if rec.state in ('disbursed',):
                raise UserError(_(
                    "Không thể đưa giải ngân ĐÃ GIẢI NGÂN về Nháp."))
            rec.state = 'draft'

    def action_cancel(self):
        for rec in self:
            if rec.state == 'disbursed':
                raise UserError(_(
                    "Không thể huỷ giải ngân đã chuyển tiền."))
            rec.state = 'cancelled'
