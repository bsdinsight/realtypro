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
    partner_id = fields.Many2one(
        'res.partner', string='Ngân hàng',
        related='credit_contract_id.partner_id', store=True, index=True,
        help='Suy từ HĐTD. Lưu lại để lọc/nhóm hạn mức theo ngân hàng — '
             'số ngân hàng có BIÊN (vài nhà tài trợ, gần như không đổi), '
             'khác với số HĐTD tăng dần theo năm.')

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
        [
         # ── A. VỐN LƯU ĐỘNG THI CÔNG (tổng thầu / thầu phụ) ──────────
         # Đặt nhãn theo NGHIỆP VỤ thi công (mẫu OCB: vật tư · nhân công ·
         # máy móc · thanh toán thầu phụ), không theo tên sản phẩm NH.
         ('wc_construction', 'VLĐ thi công · Theo hợp đồng/gói thầu'),
         ('wc_material', 'VLĐ thi công · Mua vật tư, nguyên vật liệu'),
         ('wc_labor', 'VLĐ thi công · Chi phí nhân công'),
         ('wc_subcontractor', 'VLĐ thi công · Thanh toán nhà thầu phụ'),
         ('working_capital', 'VLĐ · Bổ sung vốn lưu động chung'),

         # ── B. TÀI TRỢ KHOẢN PHẢI THU ────────────────────────────────
         # NGANG HÀNG vốn lưu động, KHÔNG lồng vào: bao thanh toán là một
         # HÌNH THỨC CẤP TÍN DỤNG riêng (TT 20/2024). Đây là chỗ IPC làm
         # TSBĐ — BIDV tài trợ tới 85% giá trị HĐ, OCB tới 80% quyền đòi nợ.
         ('ar_ipc_loan',
          'Khoản phải thu · Vay bảo đảm bằng quyền đòi nợ KL hoàn thành (IPC)'),
         ('factoring_seller',
          'Khoản phải thu · Bao thanh toán bên bán (chiết khấu phải thu)'),
         ('factoring_buyer',
          'Khoản phải thu · Bao thanh toán bên mua (tài trợ chuỗi cung ứng)'),

         # ── C. BẢO LÃNH ──────────────────────────────────────────────
         # ⚠️ 'bank_guarantee' là giá trị CHỊU LỰC — KHÔNG tách thành loại
         # BL con. Nó gate: _compute_amount_used (cộng BL đang hiệu lực),
         # credit_contract._compute_split_stats (tách vay/bảo lãnh), và
         # domain chọn facility ở re.bank.guarantee + re.guarantee.request.
         # Loại BL chi tiết nằm ở re.bank.guarantee.guarantee_type.
         ('bank_guarantee', 'Bảo lãnh ngân hàng'),

         # ── D. ĐẦU TƯ THIẾT BỊ THI CÔNG ──────────────────────────────
         ('equip_purchase', 'Thiết bị · Vay mua máy móc, thiết bị thi công'),
         ('equip_finlease', 'Thiết bị · Thuê tài chính thiết bị thi công'),

         # ── E. ĐẦU TƯ CHUNG (giữ từ bản cũ) ──────────────────────────
         ('investment_short', 'Đầu tư · Ngắn hạn'),
         ('investment_medium', 'Đầu tư · Trung hạn'),
         ('investment_long', 'Đầu tư · Dài hạn / dự án'),

         # ── F. TÀI TRỢ THƯƠNG MẠI ────────────────────────────────────
         ('lc_import_equipment',
          'Thương mại · L/C nhập khẩu thiết bị, vật tư công trình'),
         ('letter_of_credit', 'Thương mại · Tín dụng chứng từ (L/C)'),
         ('trade_finance', 'Thương mại · Tài trợ thương mại khác'),

         # ── G. DỰ ÁN BĐS (chỉ CHỦ ĐẦU TƯ) ───────────────────────────
         ('dev_project',
          'Dự án BĐS · Phát triển dự án (tiền SDĐ, GPMB, xây dựng, hạ tầng)'),
         ('dev_acquisition',
          'Dự án BĐS · Mua/nhận chuyển nhượng, M&A dự án'),
         ('dev_cooperation',
          'Dự án BĐS · Góp vốn, hợp tác đầu tư kinh doanh dự án'),
         ('dev_restructure',
          'Dự án BĐS · Tái cấu trúc nợ dự án / trái phiếu DN BĐS'),

         # ── H. KHÁC ──────────────────────────────────────────────────
         ('overdraft', 'Khác · Thấu chi'),
         ('refinance', 'Khác · Tái cấp vốn / cơ cấu nợ'),
         ('reimbursement', 'Khác · Bù đắp tài chính'),
         ('other', 'Khác'),
        ],
        string='Mục đích sử dụng vốn', required=True, default='other',
        tracking=True,
        help='Mục đích sử dụng vốn theo HĐTD. NH VN thường chia hạn mức '
             'theo mục đích (vd 50 tỷ VLĐ thi công + 30 tỷ đầu tư dự án + '
             '20 tỷ bảo lãnh). Tách bạch với Loại (facility_type) — cái đó '
             'nói hạn mức HOẠT ĐỘNG thế nào (tuần hoàn/có kỳ hạn/thấu chi).')

    purpose_restricted = fields.Boolean(
        string='Mục đích hạn chế', compute='_compute_purpose_restricted',
        help='Điều 8 khoản 8/9/10 TT 39/2016 cấm 3 nhóm nhu cầu vốn này, '
             'NHƯNG đang NGƯNG hiệu lực từ 01/9/2023 theo TT 10/2023 và '
             'chưa được khôi phục. Giữ làm CỜ CẢNH BÁO, không chặn cứng — '
             'NHNN có thể khôi phục bất cứ lúc nào; khi đó chỉ cần đổi cờ.')

    @api.depends('purpose')
    def _compute_purpose_restricted(self):
        # Điều 8 TT 39/2016: kh.8 góp vốn/mua cổ phần chưa niêm yết ·
        # kh.9 hợp đồng hợp tác vào dự án chưa đủ điều kiện KDBĐS ·
        # kh.10 bù đắp tài chính. Cả 3 đang ngưng hiệu lực (TT 10/2023).
        restricted = ('dev_acquisition', 'dev_cooperation', 'reimbursement')
        for rec in self:
            rec.purpose_restricted = rec.purpose in restricted
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
