# -*- coding: utf-8 -*-
"""
Biên bản Nghiệm thu Khối lượng (BBN KLCV) — entity LÕI Phase P1.

Chứng từ pháp lý VN xác nhận khối lượng đã thi công của 1 HĐ nhà thầu
trong 1 kỳ. NT đề xuất (date_submitted) → CĐT duyệt (date_approved).
Khối lượng nghiệm thu drive % progress của hạng mục / HĐ / dự án.

Workflow (2 bên — Phase P1):
    draft → proposed → approved
                ↘ cancelled

SLA: HĐ có thể quy định N ngày CĐT phải trả lời sau khi NT đề xuất —
hệ thống cảnh báo nếu trễ (is_overdue_response).
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class RpProgressAcceptance(models.Model):
    _name = 'rp.progress.acceptance'
    _description = 'Biên bản nghiệm thu khối lượng (BBN KLCV)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_submitted desc, id desc'

    name = fields.Char(
        string='Số BBNT', required=False, copy=False, tracking=True,
        help='Auto sinh sequence per contract khi save lần đầu. '
             'Format: BBNT-{YYYY}/{MM}-{contract_code}-{NN}.')
    contract_id = fields.Many2one(
        'rp.contract', string='HĐ nhà thầu', required=True,
        tracking=True, ondelete='restrict',
        domain="[('state', 'in', ['signed', 'in_progress'])]")
    payment_milestone_id = fields.Many2one(
        'rp.contract.payment.milestone', string='Đợt thanh toán',
        ondelete='set null', copy=False, tracking=True,
        help='BBNT này dành cho đợt thanh toán nào của HĐ.')
    project_id = fields.Many2one(
        're.project', string='Dự án',
        related='contract_id.project_id', store=True, readonly=True)
    contractor_id = fields.Many2one(
        'res.partner', string='Nhà thầu',
        related='contract_id.contractor_id', store=True, readonly=True)
    company_id = fields.Many2one(
        'res.company', string='Công ty',
        related='contract_id.company_id', store=True, readonly=True)
    currency_id = fields.Many2one(
        'res.currency', string='Loại tiền',
        related='contract_id.currency_id', store=True, readonly=True)

    # --- Thời gian ---
    date_submitted = fields.Date(
        string='Ngày NT đề xuất', tracking=True,
        default=fields.Date.context_today,
        help='Ngày Nhà thầu nộp hồ sơ nghiệm thu.')
    date_approved = fields.Date(
        string='Ngày CĐT duyệt', tracking=True, readonly=True,
        help='Ngày CĐT/tổng thầu ký duyệt.')
    deadline_response = fields.Date(
        string='Hạn trả lời (theo SLA HĐ)',
        compute='_compute_deadline_response', store=True,
        help='= Ngày đề xuất + sla_response_days của HĐ.')
    is_overdue_response = fields.Boolean(
        string='Trễ hạn trả lời',
        compute='_compute_overdue_response',
        help='True nếu hôm nay > deadline mà BBN vẫn ở proposed.')
    days_overdue = fields.Integer(
        string='Số ngày trễ',
        compute='_compute_overdue_response')

    # --- Báo cáo: kỳ nào — tự derive từ date_submitted ---
    report_year = fields.Integer(
        string='Năm', compute='_compute_report_period', store=True,
        help='Năm của ngày đề xuất — dùng cho báo cáo theo kỳ.')
    report_month = fields.Integer(
        string='Tháng', compute='_compute_report_period', store=True)

    # --- Người ký ---
    representative_contractor = fields.Char(
        string='Người ký bên NT')
    representative_owner = fields.Char(
        string='Người ký bên CĐT')

    # --- Workflow state (2 bên — P1) ---
    state = fields.Selection(
        [('draft', 'Nháp'),
         ('proposed', 'Đã đề xuất'),
         ('approved', 'CĐT duyệt'),
         ('cancelled', 'Huỷ')],
        string='Trạng thái', default='draft', required=True, tracking=True)

    # --- Lines + computed totals ---
    line_ids = fields.One2many(
        'rp.progress.acceptance.line', 'acceptance_id',
        string='Khối lượng nghiệm thu')
    line_count = fields.Integer(
        compute='_compute_totals')
    total_value_period = fields.Monetary(
        string='Σ giá trị nghiệm thu kỳ',
        compute='_compute_totals', store=True,
        help='Tổng giá trị khối lượng nghiệm thu kỳ này.')
    total_value_to_date = fields.Monetary(
        string='Σ lũy kế đến kỳ',
        compute='_compute_totals', store=True,
        help='Tổng lũy kế (gồm kỳ này + các BBN approved trước đó).')
    progress_percent = fields.Float(
        string='% hoàn thành HĐ',
        compute='_compute_progress_percent', store=True,
        help='= total_value_to_date / contract_value_pretax × 100.')

    note = fields.Text(string='Ghi chú')
    active = fields.Boolean(default=True)

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends('date_submitted')
    def _compute_report_period(self):
        for rec in self:
            if rec.date_submitted:
                rec.report_year = rec.date_submitted.year
                rec.report_month = rec.date_submitted.month
            else:
                rec.report_year = 0
                rec.report_month = 0

    @api.depends('date_submitted', 'contract_id.sla_response_days')
    def _compute_deadline_response(self):
        from datetime import timedelta
        for rec in self:
            if rec.date_submitted and rec.contract_id.sla_response_days:
                rec.deadline_response = rec.date_submitted + timedelta(
                    days=rec.contract_id.sla_response_days)
            else:
                rec.deadline_response = False

    def _compute_overdue_response(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if (rec.state == 'proposed'
                    and rec.deadline_response
                    and today > rec.deadline_response):
                rec.is_overdue_response = True
                rec.days_overdue = (today - rec.deadline_response).days
            else:
                rec.is_overdue_response = False
                rec.days_overdue = 0

    @api.depends('line_ids', 'line_ids.amount_this_period',
                 'line_ids.amount_to_date')
    def _compute_totals(self):
        for rec in self:
            rec.line_count = len(rec.line_ids)
            rec.total_value_period = sum(
                rec.line_ids.mapped('amount_this_period'))
            rec.total_value_to_date = sum(
                rec.line_ids.mapped('amount_to_date'))

    @api.depends('total_value_to_date',
                 'contract_id.contract_value_pretax')
    def _compute_progress_percent(self):
        for rec in self:
            base = rec.contract_id.contract_value_pretax
            if base:
                rec.progress_percent = (
                    rec.total_value_to_date / base * 100.0)
            else:
                rec.progress_percent = 0.0

    # ------------------------------------------------------------------
    # Create — auto sequence per contract
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            need_seq = (not vals.get('name')
                        or vals.get('name') == '/')
            if need_seq and vals.get('contract_id'):
                contract = self.env['rp.contract'].browse(vals['contract_id'])
                # Try contract-specific sequence first, fallback global
                seq_code = 'rp.progress.acceptance.%s' % contract.id
                seq = self.env['ir.sequence'].search(
                    [('code', '=', seq_code)], limit=1)
                if not seq:
                    code_part = (contract.name or 'HD').replace(' ', '')
                    seq = self.env['ir.sequence'].sudo().create({
                        'name': 'BBNT KLCV — %s' % code_part,
                        'code': seq_code,
                        # Odoo sequence prefix tokens %(year)s, %(month)s
                        # → giữ literal, concat với contract code:
                        'prefix': 'BBNT-%(year)s/%(month)s-'
                                  + code_part + '-',
                        'padding': 3,
                    })
                vals['name'] = seq.next_by_id()
        recs = super().create(vals_list)
        # Sync ngược lên milestone — nếu created từ context milestone,
        # set milestone.acceptance_id = bbnt vừa tạo.
        for rec in recs:
            if rec.payment_milestone_id and not rec.payment_milestone_id.acceptance_id:
                rec.payment_milestone_id.acceptance_id = rec.id
        return recs

    # ------------------------------------------------------------------
    # State machine
    # ------------------------------------------------------------------
    def action_propose(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_(
                    "Chỉ BBN ở trạng thái Nháp mới đề xuất được."))
            if not rec.line_ids:
                raise UserError(_(
                    "Cần ít nhất 1 dòng khối lượng trước khi đề xuất."))
            if not rec.date_submitted:
                rec.date_submitted = fields.Date.context_today(self)
            rec.state = 'proposed'
            rec.message_post(body=_("Nhà thầu đề xuất BBN."))

    def action_approve(self):
        for rec in self:
            if rec.state != 'proposed':
                raise UserError(_(
                    "Chỉ BBN đã đề xuất mới duyệt được."))
            rec.state = 'approved'
            rec.date_approved = fields.Date.context_today(self)
            rec.message_post(body=_(
                "CĐT duyệt BBN — giá trị nghiệm thu kỳ: %(p)s, "
                "lũy kế: %(t)s.",
                p=rec.total_value_period,
                t=rec.total_value_to_date))

    def action_reset_draft(self):
        for rec in self:
            if rec.state == 'approved':
                raise UserError(_(
                    "Không thể đưa BBN đã duyệt về Nháp. "
                    "Tạo BBN mới để điều chỉnh."))
            rec.state = 'draft'
            rec.date_approved = False

    def action_cancel(self):
        for rec in self:
            if rec.state == 'approved':
                raise UserError(_(
                    "Không thể huỷ BBN đã duyệt (giữ vết). "
                    "Tạo BBN điều chỉnh nếu cần."))
            rec.state = 'cancelled'

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def unlink(self):
        for rec in self:
            if rec.state == 'approved':
                raise UserError(_(
                    "Không thể xoá BBN '%s' đã duyệt. "
                    "Huỷ thay vì xoá để giữ vết.", rec.name))
        return super().unlink()

    @api.constrains('date_submitted', 'date_approved')
    def _check_dates(self):
        for rec in self:
            if (rec.date_approved and rec.date_submitted
                    and rec.date_approved < rec.date_submitted):
                raise ValidationError(_(
                    "Ngày duyệt không được trước ngày đề xuất."))
