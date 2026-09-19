# -*- coding: utf-8 -*-
"""
Dòng lịch lãi (interest schedule line) của một khế ước nhận nợ.

Lịch lãi là DỰ KIẾN (forecast) tiền lãi phải trả theo từng kỳ, sinh tự động
theo phương pháp tính lãi của KW. Cho phép override từng dòng khi ngân hàng
tính lệch do quy ước ngày.
"""
from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

# Các ô người dùng sửa được tay trên tab Lịch lãi. Sửa một trong số
# này là sửa NGHĨA VỤ TRẢ NỢ, nên phải để lại vết ở Nhật ký khế ước
# (backlog 746). Các cột "đã trả" không nằm đây: chúng do chứng từ
# trả nợ tính ra, không ai gõ tay được.
LOGGED_LINE_FIELDS = {
    'date_from': 'Từ ngày',
    'date_to': 'Đến ngày',
    'principal_base': 'Gốc tính lãi',
    'interest_rate': 'Lãi suất (%/năm)',
    'principal_due': 'Gốc kỳ',
    'interest_amount': 'Tiền lãi',
    'interest_amount_manual': 'Tiền lãi (sửa tay)',
    'is_overridden': 'Sửa tay tiền lãi',
    'fee_amount': 'Phí kỳ',
}


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
        help='Phí KW phân bổ kỳ này (khách hàng #9):\n'
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
    amount_remaining_total = fields.Monetary(
        string='Tổng còn phải trả',
        compute='_compute_amount_remaining_total', store=True,
        help='= Gốc còn phải trả + Lãi còn phải trả + Phí còn phải trả '
             '(báo cáo Lịch lãi quá hạn — backlog 1091).')
    partner_id = fields.Many2one(
        related='note_id.partner_id', store=True, string='Ngân hàng')

    is_overdue = fields.Boolean(
        string='Quá hạn chưa trả', compute='_compute_overdue_flag',
        store=True,
        help='Kỳ đã qua ngày đến hạn mà vẫn còn gốc hoặc lãi chưa trả.')
    days_overdue = fields.Integer(
        string='Số ngày quá hạn', compute='_compute_overdue_flag',
        store=True)
    amount_net_off = fields.Monetary(
        string='Tiền net-off', compute='_compute_net_off', store=True,
        help='Σ phần chênh lệch đã bù trừ vào kỳ này — cộng từ các '
             'dòng trả nợ do nút "Net-off chênh lệch" sinh ra, dù bấm '
             'ở kỳ lịch lãi hay ở dòng trích thu tự động.')
    bank_advice_line_ids = fields.One2many(
        're.loan.bank.advice.line', 'interest_line_id',
        string='Dòng trích thu chỉ định kỳ này')
    amount_overpaid = fields.Monetary(
        string='Trích dư', compute='_compute_paid_amounts', store=True,
        help='Tiền ĐÃ THU vượt nghĩa vụ của kỳ (gốc + lãi + phí), gồm '
             'hai nguồn:\n'
             '• dòng trả nợ nhập thừa cho kỳ; và\n'
             '• phần ngân hàng trích cho kỳ này nhưng KHÔNG rót hết '
             'vào kỳ (giấy báo chỉ rót tối đa bằng nghĩa vụ, phần thừa '
             'nằm lại ở "Chưa allocate" của giấy báo).\n'
             'Con số này KHÔNG mất đi sau khi net-off — nó ghi nhận là '
             'đã từng thu dư bao nhiêu.')
    has_net_off = fields.Boolean(
        string='Có net-off', compute='_compute_net_off', store=True,
        help='Kỳ có chênh lệch đã được ghi nhận — một trong hai:\n'
             '• có dòng trả nợ net-off (bù cho đủ khi ngân hàng trích '
             'thiếu), hoặc\n'
             '• bị TRÍCH DƯ (xem ô "Trích dư").\n'
             'Dùng để lọc nhanh trên Lịch lãi những kỳ không khớp '
             'tròn với nghĩa vụ.')
    net_off_allowed = fields.Boolean(
        string='Được net-off', compute='_compute_net_off_allowed',
        help='Kỳ còn chênh lệch trong ngưỡng cho phép. Vượt ngưỡng '
             'thì nút Net-off bị ẩn — phải tạo trả nợ chính thức.')

    def _compute_net_off_allowed(self):
        """Ẩn nút Net-off ở những kỳ không net-off được (backlog 758).

        Trước đây nút luôn hiện, bấm vào mới báo vượt ngưỡng. Với kỳ
        lệch cả trăm triệu thì cái nút đó chỉ là một cái bẫy bấm nhầm.

        Backlog 988: nút hiện cho CẢ HAI chiều. Chiều DƯ trước đây chỉ
        bấm được ở màn "Trích thu tự động" — người theo dõi khế ước
        đang đứng ở Lịch lãi phải bỏ màn hình đi tìm giấy báo, mà
        không có gì trên Lịch lãi nói cho họ biết là phải đi đâu.
        """
        threshold = self.env['res.config.settings'].sudo(
        ).get_net_off_threshold()
        for line in self:
            diff = ((line.amount_principal_remaining or 0.0)
                    + (line.amount_interest_remaining or 0.0))
            short_ok = (line.state != 'paid' and 0.01 < diff <= threshold)
            over = line._pending_advice_over()
            over_ok = bool(over) and 0.01 < sum(
                al.amount_unallocated for al in over) <= threshold
            line.net_off_allowed = bool(
                threshold > 0 and (short_ok or over_ok))

    def _pending_advice_over(self):
        """Dòng trích thu của kỳ này còn tiền treo, chưa net-off."""
        self.ensure_one()
        return self.bank_advice_line_ids.filtered(
            lambda al: al.state == 'posted'
            and (al.amount_unallocated or 0.0) > 0.01)

    currency_id = fields.Many2one(
        related='note_id.currency_id', store=True, readonly=True)
    company_id = fields.Many2one(
        related='note_id.company_id', store=True, readonly=True)

    @api.depends('repayment_ids.amount_principal',
                 'repayment_ids.amount_interest',
                 'repayment_ids.amount_fee',
                 'principal_due', 'interest_amount', 'fee_amount',
                 'bank_advice_line_ids.amount',
                 'bank_advice_line_ids.amount_allocated',
                 'bank_advice_line_ids.state')
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
            # Phần NGÂN HÀNG TRÍCH DƯ so với nghĩa vụ của kỳ. Ba ô
            # "còn lại" đều kẹp sàn 0 nên trả dư trước đây KHÔNG hiện
            # ra ở đâu cả: kỳ chỉ đọc là "Đã trả", còn bao nhiêu tiền
            # thừa thì màn hình Lịch lãi im lặng (backlog 988).
            due_total = ((line.principal_due or 0.0)
                         + (line.interest_amount or 0.0)
                         + (line.fee_amount or 0.0))
            # Phần ngân hàng trích CHO KỲ NÀY mà không rót hết vào kỳ.
            # Giấy báo chỉ định kỳ chỉ rót tối đa bằng nghĩa vụ, nên
            # kỳ luôn đọc là "trả vừa đủ" còn tiền thừa nằm lại ở giấy
            # báo — nhìn ở Lịch lãi không thấy gì (backlog 988).
            # Lấy `amount − đã allocate` chứ không lấy "chưa allocate":
            # số này KHÔNG đổi sau khi net-off hay phân bổ tiếp, nên
            # cột giữ được ý nghĩa "đã từng thu dư bao nhiêu".
            advice_over = sum(
                max(0.0, (al.amount or 0.0) - (al.amount_allocated or 0.0))
                for al in line.bank_advice_line_ids
                if al.state == 'posted')
            # Kẹp nghĩa vụ ở 0 trước khi trừ: gặp thật trên dữ liệu
            # một kỳ có `principal_due` ÂM (nhập tay sai). Không kẹp
            # thì kỳ chưa trả đồng nào cũng đọc ra "trích dư" đúng
            # bằng phần âm đó — một con số ma để người dùng đi tìm.
            line.amount_overpaid = max(
                0.0, (paid_p + paid_i + paid_f) - max(0.0, due_total)
            ) + advice_over
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
        """Phân bổ phí KW vào kỳ (khách hàng #9).

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
                    key=lambda l: (l.period_no or 0,
                                   l.id if isinstance(l.id, int)
                                   else float('inf')))
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

    def _formula_interest(self):
        self.ensure_one()
        return (self.principal_base * (self.interest_rate / 100.0)
                * self._day_factor())

    # is_overridden / interest_amount_manual CỐ Ý không nằm trong
    # depends (backlog 1087). Nằm trong đó thì form tính lại ngay khi
    # đang gõ: vừa bật "Sửa tay" tiền lãi đã nhảy về 0, gõ tới đâu tổng
    # phải trả đổi tới đó, dù người dùng chưa bấm Lưu và có thể bỏ.
    # Nay số chỉ đổi lúc lưu — write() bên dưới tự áp. Thân hàm vẫn tôn
    # trọng cờ sửa tay, để khi lãi suất/dư nợ đổi thì kỳ sửa tay giữ số.
    @api.depends('principal_base', 'interest_rate', 'days',
                 'note_id.day_count')
    def _compute_interest_amount(self):
        for line in self:
            if line.is_overridden:
                line.interest_amount = line.interest_amount_manual
            else:
                line.interest_amount = line._formula_interest()

    @api.onchange('is_overridden')
    def _onchange_is_overridden_prefill(self):
        # Bật sửa tay → điền sẵn số đang có để người dùng chỉnh từ đó,
        # thay vì bắt gõ lại từ con số 0.
        for line in self:
            if line.is_overridden and not line.interest_amount_manual:
                line.interest_amount_manual = line.interest_amount

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

    @api.depends('amount_principal_remaining', 'amount_interest_remaining',
                 'amount_fee_remaining')
    def _compute_amount_remaining_total(self):
        for line in self:
            line.amount_remaining_total = (
                (line.amount_principal_remaining or 0.0)
                + (line.amount_interest_remaining or 0.0)
                + (line.amount_fee_remaining or 0.0))

    @api.model
    def _refresh_overdue_flags(self, today=None):
        """Tính lại cờ/ số ngày quá hạn — hai thứ đi theo NGÀY HÔM NAY.

        Hai trường này lưu vào DB nên chỉ tự tính lại khi dữ liệu kỳ
        đổi; qua đêm mà không ai đụng vào khế ước thì kỳ vừa tới hạn hôm
        qua vẫn chưa bị đánh dấu, và số ngày trễ đứng im. Cron hằng ngày
        gọi hàm này (backlog 1091 — báo cáo Lịch lãi quá hạn đọc cờ đó).
        """
        today = today or fields.Date.context_today(self)
        lines = self.search([
            '|', ('is_overdue', '=', True),
            '&', ('date_to', '<', today), ('state', '!=', 'paid')])
        if lines:
            self.env.add_to_compute(self._fields['is_overdue'], lines)
            self.env.add_to_compute(self._fields['days_overdue'], lines)
            lines.flush_recordset(['is_overdue', 'days_overdue'])
        return lines

    # ------------------------------------------------------------------
    # Action: Thanh toán kỳ này → tạo Repayment tương ứng
    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # Vết sửa tay trên lịch lãi (backlog 746)
    # ------------------------------------------------------------------
    def write(self, vals):
        if (('is_overridden' in vals or 'interest_amount_manual' in vals)
                and 'interest_amount' not in vals):
            # Áp số sửa tay vào Tiền lãi ĐÚNG LÚC LƯU (backlog 1087) —
            # xem chú thích ở _compute_interest_amount. Chia nhóm theo
            # số lãi đích để mỗi nhóm một lần ghi, giữ một mẩu nhật ký.
            groups = {}
            for rec in self:
                overridden = vals.get('is_overridden', rec.is_overridden)
                manual = vals.get('interest_amount_manual',
                                  rec.interest_amount_manual)
                target = manual if overridden else rec._formula_interest()
                groups.setdefault(target or 0.0, self.browse())
                groups[target or 0.0] |= rec
            res = True
            for target, recs in groups.items():
                # Gọi lại write() của chính model (có interest_amount
                # trong vals nên không lặp) để phần ghi nhật ký bên
                # dưới vẫn chạy.
                res &= recs.write(dict(vals, interest_amount=target))
            return res
        watched = [f for f in vals if f in LOGGED_LINE_FIELDS]
        before = {}
        if watched and not self.env.context.get('skip_interest_line_log'):
            before = {rec.id: {f: rec[f] for f in watched} for rec in self}
        res = super().write(vals)
        if before:
            self._log_line_changes(before, watched)
        return res

    def _fmt_line_value(self, fname, value):
        field = self._fields[fname]
        if value in (False, None) and field.type != 'boolean':
            return '—'
        if field.type == 'boolean':
            return _('Có') if value else _('Không')
        if field.type == 'monetary':
            return '{:,.0f}'.format(value or 0.0)
        if field.type == 'float':
            return '{:,.2f}'.format(value or 0.0)
        return str(value)

    def _log_line_changes(self, before, watched):
        """Gộp thay đổi theo khế ước rồi ghi một mẩu vào Nhật ký.

        Ghi lên khế ước chứ không lên dòng lịch lãi: dòng lịch lãi
        nằm trong lưới nhúng, không có chỗ để đọc nhật ký của riêng
        nó, mà người kiểm tra cũng đọc theo khế ước chứ không theo kỳ.
        """
        by_note = {}
        for line in self:
            old = before.get(line.id) or {}
            rows = []
            for fname in watched:
                old_val, new_val = old.get(fname), line[fname]
                field = self._fields[fname]
                if field.type in ('monetary', 'float'):
                    if abs((old_val or 0.0) - (new_val or 0.0)) < 0.005:
                        continue
                elif old_val == new_val:
                    continue
                rows.append('%s: %s → <b>%s</b>' % (
                    LOGGED_LINE_FIELDS[fname],
                    line._fmt_line_value(fname, old_val),
                    line._fmt_line_value(fname, new_val)))
            if rows:
                by_note.setdefault(line.note_id, []).append(
                    (line.period_no, rows))
        for note, entries in by_note.items():
            if not note:
                continue
            body = [_('Sửa tay Lịch lãi:')]
            for period_no, rows in sorted(entries,
                                          key=lambda e: e[0] or 0):
                body.append('<b>%s %s</b> — %s' % (
                    _('Kỳ'), period_no or '?', '; '.join(rows)))
            note.message_post(body=Markup('<br/>'.join(body)))

    def action_create_repayment(self):
        """Mở form trả nợ đã điền sẵn số của kỳ này.

        *** KHÔNG tạo bản ghi trước khi mở hộp thoại ***
        Bản cũ create() rồi mới mở form bản ghi đó. Người dùng bấm
        "Huỷ" trên hộp thoại thì chỉ đóng cửa sổ — bản ghi trả nợ vẫn
        nằm lại và kỳ đã bị đánh dấu ĐÃ TRẢ. Nghĩa là bấm Huỷ mà tiền
        vẫn được ghi nhận (backlog 747).

        Bản này chỉ truyền giá trị mặc định vào form trống: Lưu mới
        tạo bản ghi, Huỷ thì không còn gì lại.
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
        bank = self.note_id.company_id.partner_id.bank_ids[:1]
        return {
            'type': 'ir.actions.act_window',
            'name': _('Trả nợ kỳ %s') % self.period_no,
            'res_model': 're.loan.note.repayment',
            'view_mode': 'form',
            'target': 'new',  # Dialog mode
            'context': {
                'default_note_id': self.note_id.id,
                'default_date': fields.Date.context_today(self),
                'default_amount_principal': max(
                    0, self.principal_due - self.amount_principal_paid),
                'default_amount_interest': max(
                    0, self.interest_amount - self.amount_interest_paid),
                # Gợi ý sẵn phí còn lại của kỳ (user sửa được trước Lưu).
                'default_amount_fee': max(
                    0, self.fee_amount - self.amount_fee_paid),
                'default_reference': _(
                    "Trả kỳ %(p)s của KW %(n)s",
                    p=self.period_no, n=self.note_id.name or ''),
                'default_interest_line_id': self.id,
                'default_bank_account_id': bank.id if bank else False,
                # Đánh dấu để bản ghi trả nợ ghi vết vào Nhật ký KW —
                # chỉ khi người dùng thật sự Lưu.
                'repayment_from_period': True,
            },
        }

    def action_auto_net_off_period(self):
        """Auto net-off chênh lệch lẻ trên kỳ — tạo 1 repayment
        write-off với amount = số còn phải trả (gốc + lãi) để
        paid_total = due_total và state → 'paid'.

        Use case: NH trích đủ rồi nhưng còn lệch vài đồng/vài trăm ₫
        do làm tròn. KTT click button trên kỳ → kỳ về 'paid' không
        cần tạo trích thu khác cho con số bé.

        Ngưỡng lấy từ Vay > Cấu hình > Tham số phân hệ Vay (mặc
        định 100.000 ₫).
        Vượt → UserError, KTT phải tạo repayment chính thức.
        """
        from odoo.exceptions import UserError
        THRESHOLD = self.env['res.config.settings'].sudo(
        ).get_net_off_threshold()
        Repayment = self.env['re.loan.note.repayment']
        for line in self:
            # Chiều DƯ: tiền thừa không nằm ở kỳ mà nằm ở dòng trích
            # thu (giấy báo chỉ rót tối đa bằng nghĩa vụ của kỳ). Uỷ
            # quyền sang đúng dòng đó — CÙNG một thao tác với bấm ở
            # màn "Trích thu tự động", chỉ là bấm được từ Lịch lãi.
            over = line._pending_advice_over()
            if over:
                over.action_auto_net_off()
                continue
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
            if THRESHOLD <= 0:
                raise UserError(_(
                    "Ngưỡng net-off đang đặt bằng 0 — tính năng bù "
                    "trừ chênh lệch lẻ đã tắt. Vào Vay > Cấu hình > "
                    "Tham số phân hệ Vay để bật lại, hoặc tạo trả nợ "
                    "chính thức cho chênh lệch này."))
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
                'is_net_off': True,
                'amount_net_off': total_diff,
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

    @api.depends('date_to', 'amount_principal_remaining',
                 'amount_interest_remaining', 'state')
    def _compute_overdue_flag(self):
        """Kỳ quá hạn = đã qua ngày đến hạn mà còn nợ.

        Tách khỏi trạng thái kỳ vì hai thứ trả lời hai câu khác nhau:
        trạng thái nói ĐÃ TRẢ ĐƯỢC BAO NHIÊU, cờ này nói CÓ TRỄ KHÔNG.
        Một kỳ "Trả một phần" có thể còn trong hạn, một kỳ khác cùng
        trạng thái thì đã trễ ba tháng.
        """
        today = fields.Date.context_today(self)
        for line in self:
            con_no = ((line.amount_principal_remaining or 0.0) > 0.01
                      or (line.amount_interest_remaining or 0.0) > 0.01)
            late = bool(line.date_to and line.date_to < today and con_no)
            line.is_overdue = late
            line.days_overdue = (today - line.date_to).days if late else 0

    @api.depends('repayment_ids.amount_net_off',
                 'repayment_ids.is_net_off',
                 'amount_overpaid')
    def _compute_net_off(self):
        """Số net-off của kỳ = Σ các dòng trả nợ được đánh dấu net-off.

        Đọc thẳng từ dòng trả nợ chứ không đi vòng qua giấy báo ngân
        hàng: nút "Net-off chênh lệch" trên kỳ lịch lãi tạo một dòng
        trả nợ và KHÔNG dựng phiếu giấy báo nào. Bản trước đọc qua
        giấy báo nên bấm nút xong cột này vẫn bằng 0, muốn thấy số
        phải đi lập thêm một phiếu — việc không ai cần làm.
        Đường trích thu tự động cũng gọi chính nút đó nên vào chung
        một chỗ.
        """
        for line in self:
            total = sum(
                r.amount_net_off or 0.0
                for r in line.repayment_ids if r.is_net_off)
            line.amount_net_off = total
            # Kỳ bị TRÍCH DƯ cũng được đánh dấu (backlog 988). Team
            # chốt KHÔNG xử ở cấp kỳ — chỉ cần nhìn ra kỳ nào có
            # chênh lệch, còn muốn sửa thì sửa thẳng dòng trả nợ.
            #
            # Cờ bật nhưng "Tiền net-off" vẫn để nguyên: ô đó chỉ đếm
            # dòng trả nợ net-off THẬT. Cộng số trả dư vào đó là trộn
            # hai thứ NGƯỢC CHIỀU nhau — tiền mình ghi thêm cho đủ kỳ
            # với tiền ngân hàng thu thừa — rồi tổng net-off của khế
            # ước thành một con số không đọc được.
            line.has_net_off = (abs(total) > 0.01
                                or (line.amount_overpaid or 0.0) > 0.01)

    @api.constrains('principal_due', 'note_id')
    def _check_principal_not_over_note(self):
        """Tổng gốc theo lịch không được vượt số tiền khế ước.

        Sửa tay một kỳ là chuyện thường, nhưng sửa xong tổng vượt số
        đã nhận nợ thì lịch trả nợ đòi nhiều hơn số đã vay — và dư nợ
        gốc tính từ đó sẽ âm ở kỳ cuối.
        """
        for line in self:
            note = line.note_id
            if not note or not note.amount:
                continue
            total = sum(note.interest_line_ids.mapped('principal_due'))
            if total > note.amount + 0.01:
                raise ValidationError(_(
                    'Tổng tiền gốc theo lịch (%(t)s) vượt số tiền khế '
                    'ước %(n)s (%(a)s). Chênh %(d)s.',
                    t='{:,.0f}'.format(total), n=note.name or '',
                    a='{:,.0f}'.format(note.amount),
                    d='{:,.0f}'.format(total - note.amount)))
