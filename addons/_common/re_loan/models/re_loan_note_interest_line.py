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
    line_type = fields.Selection(
        [('period',     'Kỳ lãi'),
         ('adjustment', 'Điều chỉnh')],
        string='Loại dòng', default='period', required=True,
        help='Điều chỉnh = dòng truy thu/truy hoàn sinh từ Thông báo '
             'Nợ/Có của NH (đổi lãi suất hồi tố). KHÔNG bị xoá khi '
             'regen lịch lãi.')
    adjustment_note_id = fields.Many2one(
        're.loan.adjustment.note', string='Thông báo Nợ/Có',
        readonly=True, ondelete='restrict',
        help='Thông báo NH sinh ra dòng điều chỉnh này.')
    display_name = fields.Char(
        compute='_compute_display_name', store=True)

    @api.depends('period_no', 'date_from', 'date_to', 'note_id.name')
    def _compute_display_name(self):
        """Tên hiển thị: 'Kỳ N — KW XXX (DD/MM/YYYY → DD/MM/YYYY)'.
        Dùng cho M2O lookup field 'interest_line_id'.
        """
        for line in self:
            parts = []
            if line.period_no:
                parts.append(_('Kỳ %s') % line.period_no)
            if line.note_id and line.note_id.name:
                parts.append(line.note_id.name)
            label = ' — '.join(parts) if parts else ''
            if line.date_from and line.date_to:
                label += ' (%s → %s)' % (
                    line.date_from.strftime('%d/%m/%Y'),
                    line.date_to.strftime('%d/%m/%Y'))
            line.display_name = label or _('Kỳ ?')
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
    fee_amount = fields.Monetary(
        string='Phí kỳ',
        compute='_compute_fee_amount', store=True, readonly=False,
        help='Phí KW phân bổ kỳ này (CC1 #9):\n'
             '• Mode "% trên lãi": = % phí × lãi kỳ\n'
             '• Mode "Cố định": = Tổng phí / số kỳ (kỳ cuối nhận dư '
             'làm tròn)\n'
             'Sửa tay được — kỳ đã trả không bị recompute.')
    total_due = fields.Monetary(
        string='Tổng phải trả',
        compute='_compute_total_due', store=True,
        help='= Tiền gốc phải trả + Tiền lãi + Phí kỳ.')

    state = fields.Selection(
        [('planned',      'Dự kiến'),
         ('accrued',      'Đã ghi nhận'),
         ('partial_paid', 'Trả một phần'),
         ('paid',         'Đã trả')],
        string='Trạng thái', default='planned', required=True,
        compute='_compute_paid_amounts', store=True, readonly=False)

    # ------------------------------------------------------------------
    # Paid tracking — link với repayments allocated vào kỳ này
    # ------------------------------------------------------------------
    repayment_ids = fields.One2many(
        're.loan.note.repayment', 'interest_line_id',
        string='Các đợt trả nợ allocate vào kỳ này',
        help='Repayments có interest_line_id = self. Tự tạo bởi '
             'advice.action_post hoặc nhập tay từ UI.')
    amount_principal_paid = fields.Monetary(
        string='Gốc đã trả',
        compute='_compute_paid_amounts', store=True)
    amount_interest_paid = fields.Monetary(
        string='Lãi đã trả',
        compute='_compute_paid_amounts', store=True)
    amount_principal_remaining = fields.Monetary(
        string='Gốc còn phải trả',
        compute='_compute_paid_amounts', store=True)
    amount_interest_remaining = fields.Monetary(
        string='Lãi còn phải trả',
        compute='_compute_paid_amounts', store=True)
    amount_fee_paid = fields.Monetary(
        string='Phí đã trả',
        compute='_compute_paid_amounts', store=True)
    amount_fee_remaining = fields.Monetary(
        string='Phí còn phải trả',
        compute='_compute_paid_amounts', store=True)
    amount_paid_total = fields.Monetary(
        string='Tổng đã trả',
        compute='_compute_paid_amounts', store=True)

    currency_id = fields.Many2one(
        related='note_id.currency_id', store=True, readonly=True)
    company_id = fields.Many2one(
        related='note_id.company_id', store=True, readonly=True)

    @api.depends('repayment_ids.amount_principal',
                 'repayment_ids.amount_interest',
                 'repayment_ids.amount_fee',
                 'principal_due', 'interest_amount', 'fee_amount')
    def _compute_paid_amounts(self):
        """Tổng từ repayment_ids → paid/remaining + auto-state.

        State auto:
          - paid: đủ cả gốc + lãi + phí
          - partial_paid: có trả nhưng chưa đủ
          - planned: chưa trả
        """
        for line in self:
            paid_p = sum(line.repayment_ids.mapped('amount_principal'))
            paid_i = sum(line.repayment_ids.mapped('amount_interest'))
            paid_f = sum(line.repayment_ids.mapped('amount_fee'))
            line.amount_principal_paid = paid_p
            line.amount_interest_paid = paid_i
            line.amount_fee_paid = paid_f
            line.amount_paid_total = paid_p + paid_i + paid_f
            line.amount_principal_remaining = max(
                0, line.principal_due - paid_p)
            line.amount_interest_remaining = max(
                0, line.interest_amount - paid_i)
            line.amount_fee_remaining = max(
                0, line.fee_amount - paid_f)
            # State auto: chỉ override planned/partial/paid;
            # nếu state đang 'accrued' (manual), giữ nguyên.
            if line.state == 'accrued':
                continue
            if (line.amount_principal_remaining <= 0.01
                    and line.amount_interest_remaining <= 0.01
                    and line.amount_fee_remaining <= 0.01
                    and (paid_p + paid_i + paid_f) > 0):
                line.state = 'paid'
            elif paid_p + paid_i + paid_f > 0:
                line.state = 'partial_paid'
            else:
                line.state = 'planned'

    @api.depends('note_id.fee_mode', 'note_id.fee_rate',
                 'note_id.fee_amount_total', 'interest_amount',
                 'line_type')
    def _compute_fee_amount(self):
        """Phân bổ phí KW vào kỳ (CC1 #9).

        - pct_interest: phí kỳ = fee_rate% × lãi kỳ (phí theo lãi,
          giảm dần tự nhiên)
        - fixed: chia ĐỀU các kỳ period; kỳ CUỐI nhận phần dư làm tròn
        - Dòng adjustment / KW không phí → 0
        - Kỳ ĐÃ TRẢ (paid/partial_paid) giữ nguyên — không recompute
          đè số đã chốt với NH.
        """
        for note in self.mapped('note_id'):
            note_lines = self.filtered(lambda l: l.note_id == note)
            mode = note.fee_mode
            if mode == 'pct_interest':
                for line in note_lines:
                    if line.state in ('paid', 'partial_paid'):
                        line.fee_amount = line.fee_amount
                    elif line.line_type != 'period':
                        line.fee_amount = 0
                    else:
                        line.fee_amount = (
                            note.fee_rate / 100.0) * line.interest_amount
            elif mode == 'fixed':
                # Chia đều trên TẤT CẢ period lines của note (kể cả
                # line ngoài recordset self — dùng full list để chia
                # đúng), nhưng chỉ ASSIGN cho lines trong self.
                all_period = note.interest_line_ids.filtered(
                    lambda l: l.line_type == 'period').sorted(
                    key=lambda l: (l.period_no or 0, l.id))
                n = len(all_period)
                each = round(note.fee_amount_total / n) if n else 0
                last_id = all_period[-1].id if n else False
                for line in note_lines:
                    if line.state in ('paid', 'partial_paid'):
                        line.fee_amount = line.fee_amount
                    elif line.line_type != 'period':
                        line.fee_amount = 0
                    elif line.id == last_id:
                        line.fee_amount = (
                            note.fee_amount_total - each * (n - 1))
                    else:
                        line.fee_amount = each
            else:  # none
                for line in note_lines:
                    if line.state in ('paid', 'partial_paid'):
                        line.fee_amount = line.fee_amount
                    else:
                        line.fee_amount = 0
        # Lines không có note (edge — new records)
        for line in self.filtered(lambda l: not l.note_id):
            line.fee_amount = 0

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

    @api.depends('principal_due', 'interest_amount', 'fee_amount')
    def _compute_total_due(self):
        for line in self:
            line.total_due = (line.principal_due + line.interest_amount
                              + line.fee_amount)

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
            'amount_principal': max(
                0, self.principal_due - self.amount_principal_paid),
            'amount_interest': max(
                0, self.interest_amount - self.amount_interest_paid),
            'reference': _("Trả kỳ %(p)s của KW %(n)s",
                           p=self.period_no,
                           n=self.note_id.name or ''),
            'interest_line_id': self.id,
        })
        # State sẽ auto = 'paid' qua _compute_paid_amounts
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

    def action_auto_net_off_period(self):
        """Auto net-off chênh lệch lẻ trên kỳ — tạo 1 repayment
        write-off với amount = số còn phải trả (gốc + lãi) để
        paid_total = due_total và state → 'paid'.

        Use case: NH trích đủ rồi nhưng còn lệch vài đồng/vài trăm ₫
        do làm tròn. KTT click button trên kỳ → kỳ về 'paid' không
        cần tạo trích thu khác cho con số bé.

        Threshold mặc định 100,000 ₫. Vượt → UserError, KTT phải
        tạo repayment chính thức.
        """
        from odoo.exceptions import UserError
        THRESHOLD = 100_000.0
        Repayment = self.env['re.loan.note.repayment']
        for line in self:
            if line.state == 'paid':
                raise UserError(_(
                    "Kỳ %s đã trả đủ — không có gì net-off.",
                    line.period_no))
            diff_p = line.amount_principal_remaining
            diff_i = line.amount_interest_remaining
            total_diff = diff_p + diff_i
            if total_diff <= 0.01:
                raise UserError(_(
                    "Kỳ %s không có chênh lệch — đã khớp 100%%.",
                    line.period_no))
            if total_diff > THRESHOLD:
                raise UserError(_(
                    "Chênh lệch kỳ %(p)s = %(d)s ₫ vượt ngưỡng "
                    "%(t)s ₫. Phải tạo trả nợ chính thức cho con số "
                    "này (audit trail), không net-off được.",
                    p=line.period_no,
                    d='{:,.0f}'.format(total_diff),
                    t='{:,.0f}'.format(THRESHOLD)))
            Repayment.create({
                'note_id': line.note_id.id,
                'date': fields.Date.context_today(line),
                'amount_principal': diff_p,
                'amount_interest': diff_i,
                'reference': _(
                    "Net-off chênh lệch lẻ kỳ %s") % line.period_no,
                'interest_line_id': line.id,
            })
            line.note_id.message_post(body=_(
                "Auto net-off chênh lệch lẻ kỳ %(p)s: gốc %(g)s ₫, "
                "lãi %(l)s ₫ (tổng %(t)s ₫ ≤ ngưỡng %(thr)s ₫).",
                p=line.period_no,
                g='{:,.0f}'.format(diff_p),
                l='{:,.0f}'.format(diff_i),
                t='{:,.0f}'.format(total_diff),
                thr='{:,.0f}'.format(THRESHOLD)))

    def action_view_repayments(self):
        """Mở list các repayments đã allocate vào kỳ này (manual + auto-debit)."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Repayments — Kỳ %s") % (self.period_no or '?'),
            'res_model': 're.loan.note.repayment',
            'view_mode': 'list,form',
            'domain': [('interest_line_id', '=', self.id)],
            'context': {'default_interest_line_id': self.id,
                        'default_note_id': self.note_id.id},
        }
