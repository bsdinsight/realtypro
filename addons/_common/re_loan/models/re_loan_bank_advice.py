# -*- coding: utf-8 -*-
"""Giấy báo nợ / chứng từ NH trích thu tự động (Auto-debit advice).

Workflow chuẩn NH VN:
  1. Doanh nghiệp nạp tiền vào TK thanh toán
  2. NH tự trích thu khế ước đến hạn
  3. NH gửi giấy báo nợ (debit advice) liệt kê:
     - Mỗi KW đã được trích thu
     - Số tiền trích thu
     - Tùy chọn: chỉ đích danh kỳ thanh toán nào
  4. KTT import giấy báo vào Realty Pro → auto-allocate vào các kỳ
     lãi/gốc theo thuật toán:
     - Có chỉ định kỳ: allocate vào đúng kỳ đó, ưu tiên lãi trước gốc
     - Không chỉ định: chạy từ kỳ cũ nhất, mỗi kỳ ưu tiên lãi rồi
       gốc, lặp đến hết tiền
"""
from collections import OrderedDict

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class ReLoanBankAdvice(models.Model):
    _name = 're.loan.bank.advice'
    _description = 'Giấy báo nợ NH (trích thu tự động KW)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_advice desc, id desc'

    name = fields.Char(
        string='Số giấy báo', required=True, copy=False, tracking=True,
        default=lambda self: _('/'),
        help='Auto sequence GBC/YYYY/NNNNN khi save.')
    date_advice = fields.Date(
        string='Ngày NH trích thu', required=True, tracking=True,
        default=fields.Date.context_today)
    reference = fields.Char(
        string='Số chứng từ NH', tracking=True,
        help='Số chứng từ giao dịch NH (UNC, ủy nhiệm chi, ...).')
    partner_id = fields.Many2one(
        'res.partner', string='Ngân hàng', required=True, tracking=True,
        domain="[('is_bank', '=', True)]")
    bank_account_id = fields.Many2one(
        'res.partner.bank', string='TK trích thu',
        domain="[('partner_id', '=', company_partner_id),"
               " ('bank_id.partner_id', '=', partner_id)]",
        help='Tài khoản NH của doanh nghiệp được trích thu — '
             'auto fill nếu chỉ có 1 TK tại NH này.')
    company_partner_id = fields.Many2one(
        'res.partner', readonly=True,
        compute='_compute_company_partner',
        help='Partner_id của company — dùng filter domain bank_account_id.')

    @api.depends('company_id')
    def _compute_company_partner(self):
        for rec in self:
            rec.company_partner_id = rec.company_id.partner_id

    @api.onchange('partner_id')
    def _onchange_partner_autofill_bank_account(self):
        """Khi chọn NH, auto-pick TK của my company tại NH đó."""
        self.bank_account_id = False
        if self.partner_id:
            accounts = self.env['res.partner.bank'].search([
                ('partner_id', '=', self.env.company.partner_id.id),
                ('bank_id.partner_id', '=', self.partner_id.id),
            ])
            if len(accounts) == 1:
                self.bank_account_id = accounts
    description = fields.Text(string='Diễn giải')
    line_ids = fields.One2many(
        're.loan.bank.advice.line', 'advice_id',
        string='Chi tiết các KW được trích thu')
    line_count = fields.Integer(compute='_compute_stats')
    amount_total = fields.Monetary(
        string='Tổng số tiền trích thu',
        compute='_compute_stats', store=True)
    repayment_count = fields.Integer(
        string='Số repayment đã tạo',
        compute='_compute_repayment_count')

    state = fields.Selection(
        [('draft',     'Nháp'),
         ('posted',    'Đã xác nhận'),
         ('cancelled', 'Đã huỷ')],
        string='Trạng thái', default='draft', required=True, tracking=True)

    currency_id = fields.Many2one(
        'res.currency', string='Tiền tệ', required=True,
        default=lambda self: self.env.company.currency_id)
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company,
        required=True)

    @api.depends('line_ids', 'line_ids.amount')
    def _compute_stats(self):
        for rec in self:
            rec.line_count = len(rec.line_ids)
            rec.amount_total = sum(rec.line_ids.mapped('amount'))

    @api.depends('line_ids.repayment_ids')
    def _compute_repayment_count(self):
        for rec in self:
            rec.repayment_count = sum(
                len(l.repayment_ids) for l in rec.line_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _('/'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    're.loan.bank.advice') or _('/')
        return super().create(vals_list)

    # ------------------------------------------------------------------
    # State machine
    # ------------------------------------------------------------------
    def action_post(self):
        """Xác nhận giấy báo + chạy allocation algorithm + tạo repayments."""
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_(
                    "Chỉ giấy báo Nháp mới xác nhận được."))
            if not rec.line_ids:
                raise UserError(_(
                    "Giấy báo phải có ít nhất 1 dòng KW trích thu."))
            for line in rec.line_ids:
                line._allocate_to_interest_lines()
            rec.state = 'posted'
            rec.message_post(body=_(
                "Đã xác nhận giấy báo + allocate %(c)s dòng vào "
                "các kỳ lãi của KW.",
                c=len(rec.line_ids)))

    def action_cancel(self):
        for rec in self:
            if rec.state == 'cancelled':
                continue
            # Xóa hết repayments do giấy báo này tạo
            repayments = rec.line_ids.mapped('repayment_ids')
            repayments.unlink()
            rec.state = 'cancelled'
            rec.message_post(body=_(
                "Đã huỷ giấy báo + revert %(c)s repayments.",
                c=len(repayments)))

    def action_reset_draft(self):
        for rec in self:
            if rec.state != 'cancelled':
                raise UserError(_(
                    "Chỉ giấy báo Đã huỷ mới về Nháp được."))
            rec.state = 'draft'

    def action_view_repayments(self):
        self.ensure_one()
        repayments = self.line_ids.mapped('repayment_ids')
        return {
            'type': 'ir.actions.act_window',
            'name': _("Repayments — %s") % self.name,
            'res_model': 're.loan.note.repayment',
            'view_mode': 'list,form',
            'domain': [('id', 'in', repayments.ids)],
        }


class ReLoanBankAdviceLine(models.Model):
    _name = 're.loan.bank.advice.line'
    _description = 'Dòng giấy báo — 1 KW được trích thu'
    _order = 'advice_id, id'

    advice_id = fields.Many2one(
        're.loan.bank.advice', string='Giấy báo',
        required=True, ondelete='cascade')
    note_id = fields.Many2one(
        're.loan.note', string='Khế ước nhận nợ',
        required=True,
        domain="[('state', 'in', ['active', 'partial_paid', 'overdue'])]",
        help='KW được trích thu. Chỉ hiện KW ở trạng thái Hiệu lực / '
             'Trả một phần / Quá hạn (KW Nháp/Đã gửi NH/Đã tất toán/'
             'Huỷ không trích thu được).')
    credit_contract_id = fields.Many2one(
        're.loan.credit.contract', string='HĐTD',
        related='note_id.credit_contract_id',
        store=True, readonly=True)
    interest_line_id = fields.Many2one(
        're.loan.note.interest.line', string='Kỳ thanh toán (chỉ định)',
        domain="[('note_id', '=', note_id),"
               " ('state', '!=', 'paid')]",
        help='Optional. Nếu giấy báo chỉ đích danh kỳ → allocate '
             'vào kỳ đó. Bỏ trống → algorithm tự loop kỳ cũ→mới. '
             'Chỉ hiện các kỳ chưa thanh toán đủ (state ∈ Dự kiến / '
             'Đã ghi nhận / Trả một phần).')
    amount = fields.Monetary(
        string='Số tiền trích thu', required=True,
        help='Số tiền NH đã trích từ TK doanh nghiệp cho KW này.')
    description = fields.Char(string='Diễn giải')

    repayment_ids = fields.One2many(
        're.loan.note.repayment', 'bank_advice_line_id',
        string='Các repayment đã tạo (sau khi post)')
    repayment_count = fields.Integer(compute='_compute_stats')
    amount_allocated = fields.Monetary(
        string='Đã allocate',
        compute='_compute_stats', store=True)
    amount_allocated_principal = fields.Monetary(
        string='Đã trả gốc',
        compute='_compute_stats', store=True,
        help='Σ amount_principal của các repayment đã tạo từ dòng '
             'trích thu này — gốc đã trả vào các kỳ sau khi post.')
    amount_allocated_interest = fields.Monetary(
        string='Đã trả lãi',
        compute='_compute_stats', store=True,
        help='Σ amount_interest của các repayment đã tạo từ dòng '
             'trích thu này — lãi đã trả vào các kỳ sau khi post.')
    amount_unallocated = fields.Monetary(
        string='Chưa allocate',
        compute='_compute_stats', store=True,
        help='Số tiền NH trích chưa allocate vào kỳ nào '
             '(= amount - allocated - net_off). DIFFER với chênh '
             'lệch kỳ — xem amount_diff_period.')

    # Chênh lệch CỦA KỲ — sau khi post: số kỳ còn phải trả
    # (= principal_remaining + interest_remaining)
    # Đây là số chênh lệch cần net-off theo CC1.
    amount_diff_period = fields.Monetary(
        string='Chênh lệch cần net-off',
        compute='_compute_diff_period',
        help='Số tiền của KỲ này CÒN PHẢI TRẢ sau khi NH đã trích '
             '(= gốc còn + lãi còn của kỳ). > 0 = kỳ thiếu, NH '
             'trích bớt vài đồng do làm tròn. Click "Net-off" để '
             'tự absorb nếu ≤ 100,000 ₫. Chỉ tính khi phiếu đã '
             'được đăng (state=posted) + dòng có chỉ định kỳ.')

    # Net-off chênh lệch giữa số NH trích (amount) và số allocate
    # vào các kỳ. Signed: + = NH dư (write off, ghi credit), - = NH
    # thiếu (ghi debit, kỳ sau bù).
    amount_net_off = fields.Monetary(
        string='Net-off',
        default=0.0,
        help='Số tiền net-off chênh lệch giữa số NH trích thực tế '
             'và số phải trả các kỳ. Positive: NH trả dư (write off / '
             'làm tròn). Negative: NH trích thiếu (ghi nợ, bù kỳ sau). '
             'Sau net-off: chưa allocate = amount - đã allocate - '
             'net-off → nên về 0.')
    net_off_reason = fields.Char(
        string='Lý do net-off',
        help='Diễn giải lý do bù trừ chênh lệch — vd: "Chênh lệch '
             'làm tròn lẻ", "Phí giao dịch NH", "Trích thiếu chuyển '
             'kỳ sau".')

    state = fields.Selection(
        related='advice_id.state', store=True, readonly=True)
    currency_id = fields.Many2one(
        related='advice_id.currency_id', store=True, readonly=True)
    company_id = fields.Many2one(
        related='advice_id.company_id', store=True, readonly=True)

    @api.depends('repayment_ids.amount_total',
                 'repayment_ids.amount_principal',
                 'repayment_ids.amount_interest',
                 'amount', 'amount_net_off')
    def _compute_stats(self):
        for rec in self:
            rec.repayment_count = len(rec.repayment_ids)
            allocated = sum(rec.repayment_ids.mapped('amount_total'))
            rec.amount_allocated = allocated
            rec.amount_allocated_principal = sum(
                rec.repayment_ids.mapped('amount_principal'))
            rec.amount_allocated_interest = sum(
                rec.repayment_ids.mapped('amount_interest'))
            # Sau net-off: unallocated = amount - allocated - net_off
            # Có thể âm nếu user net-off quá lớn → clamp 0
            rec.amount_unallocated = max(
                0, rec.amount - allocated - rec.amount_net_off)

    @api.depends('interest_line_id.amount_principal_remaining',
                 'interest_line_id.amount_interest_remaining',
                 'amount', 'state')
    def _compute_diff_period(self):
        """Chênh lệch tính NGAY khi user nhập 'Số tiền trích thu' (#13).

        Draft (preview):
            diff = max(0, kỳ_còn_phải_trả - số_NH_sẽ_trích)
            = ước tính chênh lệch SAU khi post.

        Posted:
            diff = kỳ_còn_phải_trả (kỳ.remaining hiện tại — đã reflect
                allocate vào kỳ rồi → chính là chênh lệch còn).

        Cần interest_line_id chỉ định để biết tính theo kỳ nào.
        """
        for rec in self:
            if not rec.interest_line_id:
                rec.amount_diff_period = 0.0
                continue
            kỳ_remaining = (
                rec.interest_line_id.amount_principal_remaining
                + rec.interest_line_id.amount_interest_remaining
            )
            if rec.state == 'posted':
                rec.amount_diff_period = kỳ_remaining
            else:
                rec.amount_diff_period = max(
                    0.0, kỳ_remaining - rec.amount)

    @api.constrains('amount')
    def _check_amount(self):
        for rec in self:
            if rec.amount <= 0:
                raise ValidationError(_(
                    "Số tiền trích thu phải > 0."))

    @api.onchange('interest_line_id')
    def _onchange_interest_line_suggest_amount(self):
        """Khi pick 1 kỳ, gợi ý 'Số tiền trích thu' = (gốc còn + lãi còn
        + phí còn) của kỳ đó (bug #21 CC1). User vẫn sửa được sau đó
        nếu NH trích ít hơn.

        Compute trực tiếp từ stored fields (principal_due, interest_amount,
        fee_amount) + sum(repayment_ids) thay vì gọi
        _compute_paid_amounts() — tránh stale cache trong onchange
        context (compute store=True dùng giá trị cache từ trước, không
        refresh kịp).
        """
        if not self.interest_line_id:
            return
        line = self.interest_line_id
        paid_p = sum(line.repayment_ids.mapped('amount_principal'))
        paid_i = sum(line.repayment_ids.mapped('amount_interest'))
        paid_f = sum(line.repayment_ids.mapped('amount_fee'))
        self.amount = (
            max(0.0, line.principal_due - paid_p)
            + max(0.0, line.interest_amount - paid_i)
            + max(0.0, line.fee_amount - paid_f)
        )

    @api.onchange('note_id')
    def _onchange_note_reset_interest_line(self):
        """Đổi KW → clear interest_line_id (vì kỳ thuộc KW khác)."""
        if self.interest_line_id and (
                self.interest_line_id.note_id != self.note_id):
            self.interest_line_id = False

    # ------------------------------------------------------------------
    # Allocation algorithm
    # ------------------------------------------------------------------
    def _allocate_to_interest_lines(self):
        """Phân bổ amount vào các kỳ lãi của note_id.

        Case A — có interest_line_id chỉ định:
          Allocate vào đúng kỳ đó. Ưu tiên: trả lãi trước (đến mức
          interest_remaining), số dư trả gốc (đến mức principal_remaining).
          Nếu vượt cả 2 → exceed = nằm lại 'unallocated'.

        Case B — không chỉ định kỳ:
          Loop interest_lines sorted theo period_no asc (cũ → mới),
          với mỗi kỳ:
            - pay_interest = min(remaining, interest_remaining_kỳ)
            - sub remaining
            - pay_principal = min(remaining, principal_remaining_kỳ)
            - sub remaining
          Lặp đến hết tiền hoặc hết kỳ.
        """
        self.ensure_one()
        # Refresh để có giá trị tính đúng
        self.note_id.interest_line_ids._compute_paid_amounts()
        Repayment = self.env['re.loan.note.repayment']
        remaining = self.amount

        def _create_repayment(il, pay_interest, pay_principal, pay_fee=0):
            """Tạo 1 repayment record cho 1 kỳ."""
            if pay_interest <= 0 and pay_principal <= 0 and pay_fee <= 0:
                return self.env['re.loan.note.repayment']
            vals = {
                'note_id': self.note_id.id,
                'date': self.advice_id.date_advice,
                'amount_principal': pay_principal,
                'amount_interest': pay_interest,
                'amount_fee': pay_fee,
                'reference': self.advice_id.reference or self.advice_id.name,
                'interest_line_id': il.id,
                'bank_advice_line_id': self.id,
            }
            return Repayment.create(vals)

        if self.interest_line_id:
            # Case A: chỉ đích danh kỳ.
            # Thứ tự allocation (CC1 #9): lãi → phí → gốc.
            il = self.interest_line_id
            il._compute_paid_amounts()
            ir = max(0, il.interest_amount - il.amount_interest_paid)
            fr = max(0, il.fee_amount - il.amount_fee_paid)
            pr = max(0, il.principal_due - il.amount_principal_paid)
            pay_interest = min(remaining, ir)
            remaining -= pay_interest
            pay_fee = min(remaining, fr)
            remaining -= pay_fee
            pay_principal = min(remaining, pr)
            remaining -= pay_principal
            _create_repayment(il, pay_interest, pay_principal, pay_fee)
            # Số dư còn lại (nếu kỳ chỉ định đã đủ) — KHÔNG auto
            # spill sang kỳ khác trong case A; nằm lại unallocated
            # cho user check.
            return

        # Case B: loop kỳ cũ → mới. Thứ tự trong kỳ: lãi → phí → gốc.
        lines = self.note_id.interest_line_ids.sorted(
            key=lambda l: (l.period_no or 0, l.date_to or fields.Date.today()))
        for il in lines:
            if remaining <= 0.01:
                break
            il._compute_paid_amounts()
            ir = max(0, il.interest_amount - il.amount_interest_paid)
            fr = max(0, il.fee_amount - il.amount_fee_paid)
            pr = max(0, il.principal_due - il.amount_principal_paid)
            if ir <= 0 and fr <= 0 and pr <= 0:
                continue  # kỳ này đã trả đủ
            pay_interest = min(remaining, ir)
            remaining -= pay_interest
            pay_fee = min(remaining, fr)
            remaining -= pay_fee
            pay_principal = min(remaining, pr)
            remaining -= pay_principal
            _create_repayment(il, pay_interest, pay_principal, pay_fee)

    def action_view_interest_lines(self):
        """Show các kỳ lãi mà line này đã thanh toán (qua repayments)."""
        self.ensure_one()
        lines = self.repayment_ids.mapped('interest_line_id')
        return {
            'type': 'ir.actions.act_window',
            'name': _("Các kỳ đã thanh toán bởi giấy báo"),
            'res_model': 're.loan.note.interest.line',
            'view_mode': 'list,form',
            'domain': [('id', 'in', lines.ids)],
        }

    def action_auto_net_off(self):
        """Net-off chênh lệch CỦA KỲ chỉ định sau khi phiếu posted.

        Delegate sang interest_line.action_auto_net_off_period — tạo
        1 repayment write-off cho kỳ với amount = remaining → kỳ về
        'paid'. Threshold 100,000 ₫.

        Conditions (CC1 #3 thêm):
          - state phải = 'posted' (phiếu đã đăng)
          - dòng phải chỉ định kỳ (interest_line_id)
          - chênh lệch > 0 và ≤ 100,000 ₫
        """
        from odoo.exceptions import UserError
        for rec in self:
            if rec.state != 'posted':
                raise UserError(_(
                    "Phiếu trích thu chưa được đăng. Net-off chỉ "
                    "khả dụng sau khi đăng phiếu."))
            if not rec.interest_line_id:
                raise UserError(_(
                    "Dòng không chỉ định kỳ thanh toán — không "
                    "net-off theo kỳ được. Tạo trả nợ riêng cho "
                    "chênh lệch nếu cần."))
            rec.interest_line_id.action_auto_net_off_period()
