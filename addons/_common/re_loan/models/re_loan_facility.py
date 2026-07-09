# -*- coding: utf-8 -*-
"""
Hạn mức tín dụng (Facility) — sub-limit dưới một HĐTD.

Mỗi facility có loại (revolving / term / thấu chi / hạn mức BL / hạn mức L/C),
số tiền hạn mức, phương pháp tính lãi mặc định. Khế ước nhận nợ (L1b) rút vốn
trong facility; amount_used / amount_available sẽ được nối vào note ở L1b.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ReLoanFacility(models.Model):
    _name = 're.loan.facility'
    _description = 'Hạn mức tín dụng (Facility)'
    _inherit = ['mail.thread']
    _order = 'credit_contract_id, id'

    name = fields.Char(string='Tên hạn mức', required=True)
    credit_contract_id = fields.Many2one(
        're.loan.credit.contract', string='HĐTD', required=True,
        ondelete='cascade', tracking=True)
    facility_type = fields.Selection(
        [('revolving', 'Tuần hoàn (Revolving)'),
         ('term', 'Có kỳ hạn (Term)'),
         ('overdraft', 'Thấu chi (Overdraft)'),
         ('guarantee_line', 'Hạn mức bảo lãnh'),
         ('lc_line', 'Hạn mức L/C')],
        string='Loại hạn mức', required=True, default='revolving',
        tracking=True,
        help='Cấu trúc kỹ thuật của hạn mức (cách hoàn lại/cam kết). '
             'Khác với Mục đích — chỉ "cái này hoạt động thế nào".')
    purpose = fields.Selection(
        [('working_capital', 'Bổ sung vốn lưu động'),
         ('investment_short', 'Đầu tư ngắn hạn'),
         ('investment_medium', 'Đầu tư trung hạn'),
         ('investment_long', 'Đầu tư dài hạn / dự án'),
         ('bank_guarantee', 'Bảo lãnh'),
         ('letter_of_credit', 'Tín dụng chứng từ (L/C)'),
         ('overdraft', 'Thấu chi'),
         ('trade_finance', 'Tài trợ thương mại'),
         ('refinance', 'Tái cấp vốn / cơ cấu nợ'),
         ('other', 'Khác')],
        string='Mục đích sử dụng vốn', required=True, default='other',
        tracking=True,
        help='Mục đích sử dụng vốn theo HĐTD. NH VN thường chia hạn mức '
             'theo mục đích (vd 50 tỷ vốn lưu động + 30 tỷ đầu tư dự án + '
             '20 tỷ bảo lãnh). Tách bạch với Loại (facility_type).')
    amount_limit = fields.Monetary(
        string='Số tiền hạn mức', required=True, tracking=True)
    date_start = fields.Date(string='Ngày bắt đầu')
    date_end = fields.Date(string='Ngày kết thúc')

    interest_rate_default = fields.Float(
        string='Lãi suất mặc định (%/năm)', digits=(5, 2),
        help='Lãi suất tham chiếu mặc định cho khế ước rút từ hạn mức này.')
    interest_method = fields.Selection(
        [('declining', 'Dư nợ giảm dần'),
         ('flat', 'Cố định trên gốc ban đầu')],
        string='Phương pháp tính lãi', default='declining', required=True,
        help='Mặc định cho khế ước; user vẫn chọn lại được trên từng KW.')
    day_count = fields.Selection(
        [('act_365', 'Thực tế / 365'),
         ('act_360', 'Thực tế / 360'),
         ('30_360', '30 / 360')],
        string='Quy ước ngày tính lãi', default='act_360', required=True,
        help='NH Việt Nam thường dùng Thực tế/360.')

    company_id = fields.Many2one(
        related='credit_contract_id.company_id', store=True, readonly=True)
    currency_id = fields.Many2one(
        related='credit_contract_id.currency_id', store=True, readonly=True)

    note_ids = fields.One2many(
        're.loan.note', 'facility_id', string='Khế ước nhận nợ')
    pledge_ids = fields.One2many(
        're.loan.collateral.pledge', 'facility_id',
        string='Tài sản thế chấp (riêng facility)',
        domain="[('pledge_target', '=', 'facility')]")
    note_count = fields.Integer(
        string='Số khế ước', compute='_compute_note_count')
    amount_used = fields.Monetary(
        string='Đã sử dụng', compute='_compute_amount_used', store=True,
        help='Cách tính phụ thuộc Loại hạn mức:\n'
             '• Tuần hoàn / Thấu chi: = Σ DƯ NỢ GỐC các KW chưa tất toán '
             '(khi trả gốc, hạn mức được KHÔI PHỤC tự động — vd KW vay 2 tỷ '
             'trả gốc 1 tỷ → đã dùng giảm còn 1 tỷ → còn lại tăng thêm 1 tỷ).\n'
             '• Có kỳ hạn / Bảo lãnh / L/C: = Σ SỐ TIỀN KW đã cam kết '
             '(không hoàn — đã rút là chiếm hạn mức đến hết kỳ).')
    amount_available = fields.Monetary(
        string='Còn lại', compute='_compute_amount_available', store=True,
        help='Hạn mức còn có thể rút thêm. Tự động cập nhật khi:\n'
             '• Tạo / huỷ KW (mọi loại)\n'
             '• Giải ngân thêm trên KW (mọi loại)\n'
             '• Trả gốc KW (CHỈ với revolving / overdraft — hoàn hạn mức)')

    flexible_limits = fields.Boolean(
        string='Hạn mức liên thông',
        default=False, tracking=True,
        help='Tick để chia sẻ phần thừa hạn mức của facility này với các '
             'facility KHÁC cũng tick liên thông (dùng chung pool). '
             'Facility KHÔNG tick = hạn mức khoá cứng cho mục đích đó, '
             'không cho mượn cũng không vay nhờ. '
             'Σ hạn mức các facility (tick hay không) đều KHÔNG được '
             'vượt tổng HĐTD.')

    project_allocation_ids = fields.One2many(
        're.loan.facility.project.allocation', 'facility_id',
        string='Phân bổ dự án')
    amount_allocated_to_projects = fields.Monetary(
        string='Đã phân bổ dự án', compute='_compute_project_allocation',
        store=True)
    amount_unallocated = fields.Monetary(
        string='Chưa phân bổ', compute='_compute_project_allocation',
        store=True)

    note = fields.Text(string='Ghi chú')
    active = fields.Boolean(default=True)

    @api.depends('project_allocation_ids.amount', 'amount_limit')
    def _compute_project_allocation(self):
        for rec in self:
            allocated = sum(rec.project_allocation_ids.mapped('amount'))
            rec.amount_allocated_to_projects = allocated
            rec.amount_unallocated = rec.amount_limit - allocated

    @api.depends('note_ids')
    def _compute_note_count(self):
        for rec in self:
            rec.note_count = len(rec.note_ids)

    @api.depends('facility_type', 'note_ids.state', 'note_ids.amount',
                 'note_ids.principal_outstanding')
    def _compute_amount_used(self):
        for rec in self:
            # Bỏ qua KW nháp/huỷ/đã tất toán hoặc giải tỏa.
            # 'fully_paid' = KW đã đóng:
            #   - Vay term/revolving: đã trả hết gốc
            #   - Bảo lãnh / L/C: BL đã giải tỏa, NH trả lại chứng thư
            # Sau khi fully_paid, hạn mức được khôi phục (không chiếm nữa).
            live = rec.note_ids.filtered(
                lambda n: n.state not in
                ('draft', 'cancelled', 'fully_paid'))
            if rec.facility_type in ('revolving', 'overdraft'):
                rec.amount_used = sum(live.mapped('principal_outstanding'))
            else:
                rec.amount_used = sum(live.mapped('amount'))

    @api.depends('amount_limit', 'amount_used', 'flexible_limits',
                 'credit_contract_id.facility_ids.amount_limit',
                 'credit_contract_id.facility_ids.amount_used',
                 'credit_contract_id.facility_ids.flexible_limits')
    def _compute_amount_available(self):
        for rec in self:
            if rec.flexible_limits and rec.credit_contract_id:
                # Pool dùng chung giữa các facility cùng tick liên thông
                # (gồm cả rec). Σ limit − Σ used trên pool.
                flex_pool = rec.credit_contract_id.facility_ids.filtered(
                    'flexible_limits')
                pool_limit = sum(flex_pool.mapped('amount_limit'))
                pool_used = sum(flex_pool.mapped('amount_used'))
                rec.amount_available = pool_limit - pool_used
            else:
                # Facility không liên thông: hạn mức cứng theo limit riêng.
                rec.amount_available = rec.amount_limit - rec.amount_used

    @api.constrains('amount_limit')
    def _check_amount_limit(self):
        for rec in self:
            if rec.amount_limit < 0:
                raise ValidationError(_(
                    "Số tiền hạn mức không được âm."))

    @api.constrains('amount_limit', 'credit_contract_id')
    def _check_within_contract(self):
        # Robust check on the facility side: @api.constrains on the
        # contract's One2many does not always fire when a facility is
        # created directly with credit_contract_id set.
        # HARD RULE: Σ limit của tất cả facility ≤ tổng HĐTD — KHÔNG
        # bypass dù tick liên thông. Liên thông chỉ đổi cách phân bổ
        # phần dư trong pool, không bypass total.
        for rec in self:
            contract = rec.credit_contract_id
            if not contract:
                continue
            total = sum(contract.facility_ids.mapped('amount_limit'))
            if total > contract.amount_total:
                raise ValidationError(_(
                    "Tổng hạn mức các facility (%(fac)s) vượt quá tổng "
                    "hạn mức HĐTD '%(name)s' (%(total)s). Σ limit luôn "
                    "phải ≤ HĐTD — tick 'Hạn mức liên thông' chỉ chia sẻ "
                    "phần thừa trong pool, không cho phép vượt total.",
                    fac=total, name=contract.name,
                    total=contract.amount_total))

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for rec in self:
            if rec.date_start and rec.date_end \
                    and rec.date_end < rec.date_start:
                raise ValidationError(_(
                    "Ngày kết thúc không được trước ngày bắt đầu."))

    def action_open_form(self):
        """Mở form đầy đủ của facility (cấu hình sâu: lãi suất, phân bổ
        dự án, TSĐB...) — dùng cho nút 'Mở' trên từng dòng trong tab
        Hạn mức của HĐTD (lưới sửa nhanh không mở được form)."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.name or _('Hạn mức (facility)'),
            'res_model': 're.loan.facility',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
