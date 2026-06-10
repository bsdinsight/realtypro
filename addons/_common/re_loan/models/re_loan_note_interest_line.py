# -*- coding: utf-8 -*-
"""
Dòng lịch lãi (interest schedule line) của một khế ước nhận nợ.

Lịch lãi là DỰ KIẾN (forecast) tiền lãi phải trả theo từng kỳ, sinh tự động
theo phương pháp tính lãi của KW. Cho phép override từng dòng khi ngân hàng
tính lệch do quy ước ngày.
"""
from odoo import _, api, fields, models


class ReLoanNoteInterestLine(models.Model):
    _name = 're.loan.note.interest.line'
    _description = 'Dòng lịch lãi khế ước'
    _order = 'note_id, period_no, id'

    note_id = fields.Many2one(
        're.loan.note', string='Khế ước', required=True, ondelete='cascade')
    period_no = fields.Integer(string='Kỳ')
    date_from = fields.Date(string='Từ ngày', required=True)
    date_to = fields.Date(string='Đến ngày', required=True)
    days = fields.Integer(string='Số ngày', compute='_compute_days', store=True)
    principal_base = fields.Monetary(
        string='Dư nợ tính lãi', required=True,
        help='Cơ sở tính lãi của kỳ (dư nợ đầu kỳ với phương pháp giảm dần, '
             'hoặc gốc ban đầu với phương pháp cố định).')
    interest_rate = fields.Float(string='Lãi suất (%/năm)', digits=(5, 2))
    interest_amount = fields.Monetary(
        string='Tiền lãi', compute='_compute_interest_amount', store=True,
        readonly=False)
    is_overridden = fields.Boolean(
        string='Sửa tay',
        help='Bật để nhập tiền lãi thủ công (khi NH tính lệch).')
    interest_amount_manual = fields.Monetary(string='Tiền lãi (sửa tay)')

    principal_due = fields.Monetary(
        string='Tiền gốc phải trả',
        compute='_compute_principal_due', store=True, readonly=False,
        help='Số tiền gốc phải trả kỳ này, tự tính theo Kế hoạch trả gốc:\n'
             '• Trả gốc cuối kỳ (Bullet): các kỳ 0đ, kỳ cuối = full gốc\n'
             '• Trả gốc đều: mỗi kỳ = số tiền KW / số kỳ\n'
             '• Tuỳ chỉnh: user nhập tay từng dòng')
    total_due = fields.Monetary(
        string='Tổng phải trả',
        compute='_compute_total_due', store=True,
        help='= Tiền gốc phải trả + Tiền lãi.')

    state = fields.Selection(
        [('planned', 'Dự kiến'),
         ('accrued', 'Đã ghi nhận'),
         ('paid', 'Đã trả')],
        string='Trạng thái', default='planned', required=True)

    currency_id = fields.Many2one(
        related='note_id.currency_id', store=True, readonly=True)
    company_id = fields.Many2one(
        related='note_id.company_id', store=True, readonly=True)

    @api.depends('date_from', 'date_to')
    def _compute_days(self):
        for line in self:
            if line.date_from and line.date_to:
                line.days = (line.date_to - line.date_from).days
            else:
                line.days = 0

    def _day_factor(self):
        """Hệ số ngày theo quy ước day_count của KW."""
        self.ensure_one()
        dc = self.note_id.day_count
        if dc == 'act_360':
            return self.days / 360.0
        if dc == '30_360':
            return 30.0 / 360.0
        # act_365 (mặc định)
        return self.days / 365.0

    @api.depends('principal_base', 'interest_rate', 'days',
                 'is_overridden', 'interest_amount_manual',
                 'note_id.day_count')
    def _compute_interest_amount(self):
        for line in self:
            if line.is_overridden:
                line.interest_amount = line.interest_amount_manual
            else:
                line.interest_amount = (
                    line.principal_base * (line.interest_rate / 100.0)
                    * line._day_factor())

    @api.depends('note_id.repayment_plan', 'note_id.amount',
                 'note_id.tenor_months', 'period_no')
    def _compute_principal_due(self):
        """Tiền gốc phải trả theo Kế hoạch trả gốc của KW.

        bullet:          period_no < n → 0; period_no == n → full amount
        equal_principal: amount / n cho mọi kỳ
        custom:          0 mặc định, user nhập tay (readonly=False)
        """
        for line in self:
            note = line.note_id
            n = note.tenor_months or 0
            plan = note.repayment_plan
            if not n or not plan:
                line.principal_due = 0.0
                continue
            if plan == 'equal_principal':
                line.principal_due = note.amount / n
            elif plan == 'bullet':
                line.principal_due = (
                    note.amount if line.period_no == n else 0.0)
            else:
                # custom: giữ giá trị hiện tại; tránh ghi đè input user.
                # On create, Odoo sẽ set 0 mặc định.
                line.principal_due = line.principal_due or 0.0

    @api.depends('principal_due', 'interest_amount')
    def _compute_total_due(self):
        for line in self:
            line.total_due = line.principal_due + line.interest_amount

    # ------------------------------------------------------------------
    # Action: Thanh toán kỳ này → tạo Repayment tương ứng
    # ------------------------------------------------------------------
    def action_create_repayment(self):
        """Tạo 1 dòng re.loan.note.repayment từ dòng lịch lãi này:
          - amount_principal = principal_due
          - amount_interest = interest_amount (hoặc manual nếu sửa tay)
          - date = ngày hôm nay
          - reference = "Trả kỳ N của KW X"

        Trả về action mở form repayment vừa tạo cho user review/edit.
        """
        from odoo.exceptions import UserError
        self.ensure_one()
        if self.state == 'paid':
            raise UserError(_(
                "Dòng lịch lãi kỳ %s đã ghi nhận thanh toán.",
                self.period_no))
        if self.total_due <= 0:
            raise UserError(_(
                "Tổng phải trả kỳ này = 0, không cần tạo thanh toán."))
        repayment = self.env['re.loan.note.repayment'].create({
            'note_id': self.note_id.id,
            'date': fields.Date.context_today(self),
            'amount_principal': self.principal_due,
            'amount_interest': self.interest_amount,
            'reference': _("Trả kỳ %(p)s của KW %(n)s",
                           p=self.period_no,
                           n=self.note_id.name or ''),
        })
        # Đánh dấu dòng lịch lãi đã thanh toán
        self.state = 'paid'
        self.note_id.message_post(body=_(
            "Tạo thanh toán từ Lịch lãi kỳ %(p)s: gốc %(g)s, lãi %(l)s.",
            p=self.period_no,
            g=self.principal_due,
            l=self.interest_amount))
        # Mở form repayment vừa tạo cho user xem/sửa
        return {
            'type': 'ir.actions.act_window',
            'name': _('Trả nợ kỳ %s') % self.period_no,
            'res_model': 're.loan.note.repayment',
            'res_id': repayment.id,
            'view_mode': 'form',
            'target': 'new',  # Dialog mode
        }
