# -*- coding: utf-8 -*-
"""Tạm ứng (Advance Payment) cho HĐ nhà thầu / NCC.

State machine:
    draft → to_approve → approved → paid → settled
                                         └→ cancelled (any state trừ settled)

Workflow:
  1. KTT tạo Tạm ứng cho HĐ nhà thầu (rp.contract) hoặc PO (purchase.order)
  2. Submit → Chờ duyệt
  3. Manager phê duyệt → Đã duyệt
  4. KW giải ngân Tạm ứng (qua Hồ sơ giải ngân pick advance_payment_id)
     → khi KW activate: Tạm ứng → 'paid'
  5. Sau khi có hóa đơn từ nhà thầu/NCC: KTT cấn trừ thủ công vào invoice
     qua rp.advance.settlement (1 Tạm ứng → nhiều Hóa đơn)
  6. amount_settled = amount → 'settled'
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


ADVANCE_STATES = [
    ('draft',      'Nháp'),
    ('to_approve', 'Chờ duyệt'),
    ('approved',   'Đã duyệt'),
    ('paid',       'Đã thanh toán'),
    ('settled',    'Đã cấn trừ đủ'),
    ('cancelled',  'Đã huỷ'),
]


class RpAdvancePayment(models.Model):
    _name = 'rp.advance.payment'
    _description = 'Tạm ứng cho HĐ nhà thầu / NCC'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_request desc, id desc'

    name = fields.Char(
        string='Số tạm ứng', required=True, copy=False, tracking=True,
        default=lambda self: _('/'),
        help='Auto sequence TU/YYYY/NNNN khi save.')

    # Liên kết đối tượng cần tạm ứng: 1 trong 2
    contract_id = fields.Many2one(
        'rp.contract', string='HĐ nhà thầu',
        tracking=True, ondelete='restrict',
        help='HĐ nhà thầu mà Tạm ứng này áp dụng. Required nếu KHÔNG '
             'có Purchase Order.')
    purchase_order_id = fields.Many2one(
        'purchase.order', string='PO mua hàng',
        tracking=True, ondelete='restrict',
        help='Purchase Order mà Tạm ứng này áp dụng. Required nếu '
             'KHÔNG có HĐ nhà thầu.')
    partner_id = fields.Many2one(
        'res.partner', string='Bên nhận tạm ứng',
        compute='_compute_partner', store=True, readonly=False,
        tracking=True,
        help='Nhà thầu hoặc Nhà cung cấp nhận tạm ứng. Auto-fill từ '
             'HĐ/PO; sửa được nếu cần.')

    amount = fields.Monetary(
        string='Giá trị tạm ứng', required=True, tracking=True,
        help='Tổng giá trị tạm ứng cần thanh toán bằng KW.')
    purpose = fields.Char(
        string='Mục đích', tracking=True,
        help='Mục đích tạm ứng (vd "Tạm ứng vật tư đợt 1", "Mua bê tông")')
    description = fields.Text(string='Diễn giải / ghi chú')

    # Ngày tracking
    date_request = fields.Date(
        string='Ngày đề nghị', required=True, tracking=True,
        default=fields.Date.context_today)
    date_approval = fields.Date(
        string='Ngày duyệt', readonly=True, tracking=True)
    date_paid = fields.Date(
        string='Ngày thanh toán', readonly=True, tracking=True)
    date_settled = fields.Date(
        string='Ngày cấn trừ đủ', readonly=True, tracking=True)

    # User
    user_id_request = fields.Many2one(
        'res.users', string='Người đề nghị', tracking=True,
        default=lambda self: self.env.user)
    user_id_approval = fields.Many2one(
        'res.users', string='Người duyệt', readonly=True, tracking=True)

    state = fields.Selection(
        ADVANCE_STATES, string='Trạng thái', default='draft',
        required=True, tracking=True)

    # Liên kết KW giải ngân tạm ứng
    # Khi tạm ứng được giải ngân bằng KW qua Hồ sơ giải ngân, link ngược
    disbursement_dossier_id = fields.Many2one(
        'rp.loan.disbursement.dossier',
        string='Hồ sơ giải ngân thanh toán',
        readonly=True, copy=False,
        help='Hồ sơ giải ngân pick Tạm ứng này → KW activate → Tạm ứng paid.')
    note_id = fields.Many2one(
        're.loan.note', string='KW giải ngân',
        related='disbursement_dossier_id.disbursement_id.note_id',
        store=True, readonly=True)

    # Cấn trừ vào hóa đơn
    settlement_ids = fields.One2many(
        'rp.advance.settlement', 'advance_id',
        string='Cấn trừ vào hóa đơn',
        readonly=False)
    amount_settled = fields.Monetary(
        string='Đã cấn trừ',
        compute='_compute_settled', store=True,
        help='Tổng số tiền đã cấn trừ vào các hóa đơn.')
    amount_remaining = fields.Monetary(
        string='Còn lại',
        compute='_compute_settled', store=True,
        help='= Giá trị tạm ứng - Đã cấn trừ. Khi = 0 → state settled.')
    settlement_count = fields.Integer(
        compute='_compute_settled', store=True)

    currency_id = fields.Many2one(
        'res.currency', required=True,
        default=lambda self: self.env.company.currency_id)
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company,
        required=True)

    # ------------------------------------------------------------------
    # Compute
    # ------------------------------------------------------------------
    @api.depends('contract_id', 'contract_id.contractor_id',
                 'purchase_order_id', 'purchase_order_id.partner_id')
    def _compute_partner(self):
        for rec in self:
            if rec.contract_id and rec.contract_id.contractor_id:
                rec.partner_id = rec.contract_id.contractor_id
            elif rec.purchase_order_id and rec.purchase_order_id.partner_id:
                rec.partner_id = rec.purchase_order_id.partner_id

    @api.depends('settlement_ids.amount', 'amount')
    def _compute_settled(self):
        for rec in self:
            settled = sum(rec.settlement_ids.mapped('amount'))
            rec.amount_settled = settled
            rec.amount_remaining = max(0.0, rec.amount - settled)
            rec.settlement_count = len(rec.settlement_ids)

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------
    @api.constrains('contract_id', 'purchase_order_id')
    def _check_one_target(self):
        for rec in self:
            if not rec.contract_id and not rec.purchase_order_id:
                raise ValidationError(_(
                    "Phải chỉ định ÍT NHẤT một trong hai: HĐ nhà thầu "
                    "HOẶC Purchase Order."))
            if rec.contract_id and rec.purchase_order_id:
                raise ValidationError(_(
                    "Chỉ chọn 1 trong 2: HĐ nhà thầu HOẶC PO. KHÔNG "
                    "chọn cả hai cho 1 Tạm ứng."))

    @api.constrains('amount')
    def _check_amount(self):
        for rec in self:
            if rec.amount <= 0:
                raise ValidationError(_(
                    "Giá trị tạm ứng phải > 0."))

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _('/'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'rp.advance.payment') or _('/')
        return super().create(vals_list)

    def unlink(self):
        for rec in self:
            if rec.state not in ('draft', 'cancelled'):
                raise UserError(_(
                    "Chỉ xoá được Tạm ứng ở trạng thái Nháp hoặc Đã huỷ. "
                    "Tạm ứng %s đang %s.", rec.name, rec.state))
        return super().unlink()

    # ------------------------------------------------------------------
    # Workflow buttons
    # ------------------------------------------------------------------
    def action_submit(self):
        """Nháp → Chờ duyệt."""
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_(
                    "Chỉ Tạm ứng Nháp mới gửi duyệt được."))
            rec.state = 'to_approve'
            rec.message_post(body=_(
                "Đã gửi duyệt — chờ Manager phê duyệt."))

    def action_approve(self):
        """Chờ duyệt → Đã duyệt. Cần group rp_advance_payment.group_manager."""
        manager_group = self.env.ref(
            'rp_advance_payment.group_advance_manager',
            raise_if_not_found=False)
        is_manager = manager_group and (
            self.env.user.id in manager_group.users.ids)
        for rec in self:
            if rec.state != 'to_approve':
                raise UserError(_(
                    "Chỉ Tạm ứng Chờ duyệt mới phê duyệt được."))
            if not is_manager and not self.env.user._is_admin():
                raise UserError(_(
                    "Bạn KHÔNG có quyền phê duyệt Tạm ứng. Cần group "
                    "'Tạm ứng / Manager'."))
            rec.state = 'approved'
            rec.date_approval = fields.Date.context_today(rec)
            rec.user_id_approval = self.env.user
            rec.message_post(body=_(
                "Đã phê duyệt Tạm ứng %(n)s (%(amt)s ₫). "
                "Sẵn sàng giải ngân qua KW.",
                n=rec.name,
                amt='{:,.0f}'.format(rec.amount)))

    def action_reject(self):
        """Chờ duyệt → Nháp (manager từ chối)."""
        for rec in self:
            if rec.state != 'to_approve':
                raise UserError(_(
                    "Chỉ Tạm ứng Chờ duyệt mới từ chối được."))
            rec.state = 'draft'
            rec.message_post(body=_(
                "Đã từ chối, quay về Nháp."))

    def action_mark_paid(self):
        """Đã duyệt → Đã thanh toán (KW giải ngân xong).

        Method này được gọi từ re.loan.note.activate() khi Hồ sơ giải
        ngân của KW có advance_payment_id. Cũng có thể gọi tay nếu
        thanh toán tạm ứng KHÔNG qua KW (vd tiền mặt).
        """
        for rec in self:
            if rec.state != 'approved':
                raise UserError(_(
                    "Chỉ Tạm ứng Đã duyệt mới chuyển 'Đã thanh toán' "
                    "được. Hiện %s.", rec.state))
            rec.state = 'paid'
            rec.date_paid = fields.Date.context_today(rec)
            rec.message_post(body=_(
                "Đã thanh toán Tạm ứng — sẵn sàng cấn trừ vào hóa đơn."))

    def action_cancel(self):
        for rec in self:
            if rec.state == 'settled':
                raise UserError(_(
                    "Tạm ứng đã cấn trừ đủ, KHÔNG huỷ được. Tạo "
                    "phiếu điều chỉnh kế toán nếu cần."))
            if rec.state == 'paid' and rec.amount_settled > 0:
                raise UserError(_(
                    "Tạm ứng đã thanh toán và có cấn trừ. Phải xoá "
                    "các dòng cấn trừ trước khi huỷ."))
            rec.state = 'cancelled'
            rec.message_post(body=_("Đã huỷ Tạm ứng."))

    def action_reset_draft(self):
        for rec in self:
            if rec.state != 'cancelled':
                raise UserError(_(
                    "Chỉ Tạm ứng Đã huỷ mới về Nháp được."))
            rec.state = 'draft'

    def action_view_settlements(self):
        """Stat button: mở list cấn trừ của Tạm ứng này."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Cấn trừ — %s") % self.name,
            'res_model': 'rp.advance.settlement',
            'view_mode': 'list,form',
            'domain': [('advance_id', '=', self.id)],
            'context': {'default_advance_id': self.id},
        }

    # ------------------------------------------------------------------
    # Auto-state khi cấn trừ đủ
    # ------------------------------------------------------------------
    def _check_fully_settled(self):
        """Sau khi settlement thay đổi → check nếu cấn trừ đủ → settled."""
        for rec in self:
            if rec.state != 'paid':
                continue
            if rec.amount_remaining <= 0.01:
                rec.state = 'settled'
                rec.date_settled = fields.Date.context_today(rec)
                rec.message_post(body=_(
                    "Tạm ứng đã được cấn trừ đủ vào hóa đơn. "
                    "Tổng cấn trừ: %(s)s ₫ / %(t)s ₫.",
                    s='{:,.0f}'.format(rec.amount_settled),
                    t='{:,.0f}'.format(rec.amount)))
