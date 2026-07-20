# -*- coding: utf-8 -*-
"""BBNT sản lượng ĐẦU RA — tổng thầu nghiệm thu VỚI Chủ đầu tư.

Mỗi BBNT = 1 kỳ sản lượng được CĐT xác nhận (giá trị trước thuế).
Workflow 2 bên: Nháp → Đã đề xuất → CĐT duyệt / Huỷ. Chỉ BBNT
'approved' được cộng vào sản lượng lũy kế / khoản phải thu.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class RpOwnerAcceptance(models.Model):
    _name = 'rp.owner.acceptance'
    _description = 'Hồ sơ nghiệm thu với Chủ đầu tư'
    _inherit = ['mail.thread']
    _order = 'date_submitted desc, id desc'

    name = fields.Char(
        string='Số BBNT', required=True, copy=False,
        default=lambda self: _('/'),
        help='Auto sinh OBBNT/YYYY/NNNN khi lưu — sửa được theo số văn '
             'bản thực tế ký với CĐT.')
    contract_id = fields.Many2one(
        'rp.owner.contract', string='HĐ với CĐT', required=True,
        ondelete='cascade', index=True)
    project_id = fields.Many2one(
        related='contract_id.project_id', store=True, index=True)
    owner_id = fields.Many2one(
        related='contract_id.owner_id', store=True,
        string='Chủ đầu tư')
    currency_id = fields.Many2one(
        related='contract_id.currency_id', store=True)
    company_id = fields.Many2one(
        related='contract_id.company_id', store=True)

    date_submitted = fields.Date(
        string='Ngày đề xuất', required=True,
        default=fields.Date.context_today, tracking=True)
    date_approved = fields.Date(
        string='Ngày CĐT duyệt', readonly=True, tracking=True)
    amount_this_period = fields.Monetary(
        string='Sản lượng kỳ này (Gross)', required=True, tracking=True,
        help='Giá trị sản lượng (trước thuế) theo biên bản kỳ này — số '
             'GỘP, chưa trừ thu hồi tạm ứng / giữ lại / back-charge. Cho '
             'phép ÂM khi CĐT điều chỉnh giảm sản lượng đã nghiệm thu '
             '(cắt khối lượng sau kiểm toán) — theo biên bản điều chỉnh.')

    # --- Giảm trừ: gợi ý theo điều khoản HĐ, SỬA TAY được (có log) ---
    advance_recovery = fields.Monetary(
        string='Thu hồi tạm ứng', tracking=True,
        compute='_compute_deductions', store=True, readonly=False,
        help='Gợi ý = Gross × %thu hồi (không vượt số dư tạm ứng còn '
             'lại). Sửa tay được khi biên bản với CĐT khác công thức.')
    retention_amount = fields.Monetary(
        string='Giữ lại (retention)', tracking=True,
        compute='_compute_deductions', store=True, readonly=False,
        help='Gợi ý = Gross × %giữ lại, chặn theo trần luỹ kế của HĐ. '
             'Đây là tiền CĐT giữ hợp pháp — CHƯA đòi được, nên không '
             'được tính vào quyền đòi nợ/TSBĐ.')
    backcharge = fields.Monetary(
        string='Back-charge', tracking=True,
        help='Khoản CĐT khấu trừ tổng thầu trong kỳ (nếu có).')
    adjustment = fields.Monetary(
        string='Điều chỉnh khác (±)', tracking=True,
        help='Chênh lệch khi CĐT duyệt KHÁC giá trị đề nghị: ghi ÂM phần '
             'bị cắt kèm lý do ở Ghi chú, để phần chênh không biến mất '
             'im lặng (còn dấu vết để khiếu nại/claim sau).')
    amount_certified = fields.Monetary(
        string='Quyền đòi nợ phát sinh', tracking=True,
        compute='_compute_net', store=True,
        help='= Gross − Giữ lại − Back-charge ± Điều chỉnh.\n'
             'ĐÂY là số cộng vào khoản phải thu / borrowing base: phần '
             'giá trị CĐT thừa nhận NỢ. Cố ý KHÔNG trừ thu hồi tạm ứng '
             '— tiền tạm ứng đã nằm trong "CĐT đã thanh toán", trừ nữa '
             'là trừ hai lần.')
    amount_net = fields.Monetary(
        string='Tiền CĐT chuyển kỳ này', tracking=True,
        compute='_compute_net', store=True,
        help='= Quyền đòi nợ phát sinh − Thu hồi tạm ứng.\n'
             'Đây là số tiền thực CĐT chuyển đợt này (dùng để lập đề '
             'nghị thanh toán / hoá đơn), KHÁC với quyền đòi nợ.')

    state = fields.Selection(
        [('draft', 'Nháp'),
         ('proposed', 'Đã đề xuất'),
         ('approved', 'CĐT duyệt'),
         ('cancelled', 'Huỷ')],
        string='Trạng thái', default='draft', required=True, tracking=True)

    ipc_id = fields.Many2one(
        'rp.owner.ipc', string='Thuộc IPC', copy=False, index=True,
        ondelete='set null',
        help='Hồ sơ thanh toán (IPC) đã gom BBNT này. Mỗi BBNT chỉ thuộc '
             'TỐI ĐA 1 IPC — chặn cùng khối lượng vào hai hồ sơ.')
    ipc_state = fields.Selection(
        related='ipc_id.state', string='Trạng thái IPC', store=True)

    note = fields.Text(string='Ghi chú')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _('/'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'rp.owner.acceptance') or _('/')
        return super().create(vals_list)

    # ------------------------------------------------------------------
    # Gross → Net
    # ------------------------------------------------------------------
    @api.depends('amount_this_period',
                 'contract_id.retention_percent',
                 'contract_id.retention_cap_percent',
                 'contract_id.contract_value_pretax',
                 'contract_id.advance_amount',
                 'contract_id.advance_recovery_percent',
                 'contract_id.acceptance_ids.amount_this_period',
                 'contract_id.acceptance_ids.state')
    def _compute_deductions(self):
        """Gợi ý 2 khoản giảm trừ theo điều khoản HĐ.

        Cố ý KHÔNG đọc `retention_amount`/`advance_recovery` của các BBNT
        anh em (tính lại từ công thức) — đọc field stored của bản ghi
        cùng model sẽ gây đệ quy compute.
        """
        for rec in self:
            c = rec.contract_id
            gross = rec.amount_this_period or 0.0
            if not c or gross <= 0:
                # BBNT điều chỉnh giảm (âm) không sinh giảm trừ mới
                rec.advance_recovery = 0.0
                rec.retention_amount = 0.0
                continue

            others = c.acceptance_ids.filtered(
                lambda a: a.state == 'approved' and a.id != rec.id
                and (a.amount_this_period or 0.0) > 0)
            other_gross = sum(others.mapped('amount_this_period'))

            # --- Thu hồi tạm ứng: không vượt số dư còn lại ---
            rate_adv = (c.advance_recovery_percent or 0.0) / 100.0
            recovered = other_gross * rate_adv
            balance = max(0.0, (c.advance_amount or 0.0) - recovered)
            rec.advance_recovery = min(gross * rate_adv, balance)

            # --- Giữ lại: chặn theo trần luỹ kế ---
            rate_ret = (c.retention_percent or 0.0) / 100.0
            cap = (c.contract_value_pretax or 0.0) * (
                (c.retention_cap_percent or 0.0) / 100.0)
            held = other_gross * rate_ret
            room = max(0.0, cap - held) if cap else gross * rate_ret
            rec.retention_amount = min(gross * rate_ret, room)

    @api.depends('amount_this_period', 'advance_recovery',
                 'retention_amount', 'backcharge', 'adjustment')
    def _compute_net(self):
        for rec in self:
            rec.amount_certified = (
                (rec.amount_this_period or 0.0)
                - (rec.retention_amount or 0.0)
                - (rec.backcharge or 0.0)
                + (rec.adjustment or 0.0))
            rec.amount_net = (
                rec.amount_certified - (rec.advance_recovery or 0.0))

    @api.constrains('amount_this_period', 'advance_recovery',
                    'retention_amount', 'backcharge')
    def _check_deductions(self):
        for rec in self:
            if (rec.amount_this_period or 0.0) <= 0:
                continue
            for val, label in ((rec.advance_recovery, 'Thu hồi tạm ứng'),
                               (rec.retention_amount, 'Giữ lại'),
                               (rec.backcharge, 'Back-charge')):
                if (val or 0.0) < 0:
                    raise ValidationError(_(
                        '%s không được âm.', label))
            total = ((rec.advance_recovery or 0.0)
                     + (rec.retention_amount or 0.0)
                     + (rec.backcharge or 0.0))
            if total > rec.amount_this_period + 0.01:
                raise ValidationError(_(
                    'Tổng giảm trừ (%(d)s) vượt sản lượng gross '
                    '(%(g)s) của BBNT %(n)s.',
                    d='{:,.0f}'.format(total),
                    g='{:,.0f}'.format(rec.amount_this_period),
                    n=rec.name))

    @api.constrains('amount_this_period')
    def _check_amount(self):
        for rec in self:
            if not rec.amount_this_period:
                raise ValidationError(
                    'Giá trị sản lượng kỳ này phải khác 0 '
                    '(âm = điều chỉnh giảm theo biên bản với CĐT).')

    # --- Workflow ---
    def action_propose(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Chỉ BBNT Nháp mới đề xuất được.'))
            rec.state = 'proposed'

    def action_approve(self):
        for rec in self:
            if rec.state != 'proposed':
                raise UserError(_(
                    'Chỉ BBNT Đã đề xuất mới ghi nhận CĐT duyệt được.'))
            # Chặn sản lượng lũy kế vượt giá trị HĐ (cần phụ lục tăng
            # giá trị HĐ trước khi nghiệm thu vượt)
            contract = rec.contract_id
            new_total = rec.amount_this_period + sum(
                contract.acceptance_ids.filtered(
                    lambda a: a.state == 'approved' and a.id != rec.id
                ).mapped('amount_this_period'))
            if new_total > contract.contract_value_pretax + 0.01:
                raise UserError(_(
                    'Sản lượng lũy kế (%(t)s) vượt giá trị HĐ '
                    '(%(v)s). Điều chỉnh giá trị HĐ (phụ lục với CĐT) '
                    'trước khi duyệt BBNT này.',
                    t='{:,.0f}'.format(new_total),
                    v='{:,.0f}'.format(contract.contract_value_pretax)))
            rec.state = 'approved'
            rec.date_approved = fields.Date.context_today(rec)
            rec.message_post(body=_(
                'CĐT duyệt BBNT %(n)s — gross %(g)s − thu hồi tạm ứng '
                '%(r)s − giữ lại %(h)s − back-charge %(b)s ± điều chỉnh '
                '%(j)s = <b>ròng %(a)s</b>.',
                n=rec.name,
                g='{:,.0f}'.format(rec.amount_this_period),
                r='{:,.0f}'.format(rec.advance_recovery or 0.0),
                h='{:,.0f}'.format(rec.retention_amount or 0.0),
                b='{:,.0f}'.format(rec.backcharge or 0.0),
                j='{:,.0f}'.format(rec.adjustment or 0.0),
                a='{:,.0f}'.format(rec.amount_net)))

    def action_reset_draft(self):
        for rec in self:
            if rec.state not in ('proposed', 'cancelled'):
                raise UserError(_(
                    'Chỉ reset được BBNT Đã đề xuất hoặc Huỷ.'))
            rec.state = 'draft'

    def action_cancel(self):
        for rec in self:
            if rec.state == 'approved':
                raise UserError(_(
                    'BBNT đã được CĐT duyệt — không huỷ được (ảnh hưởng '
                    'phải thu/TSBĐ). Cần điều chỉnh thì lập BBNT âm kỳ '
                    'sau theo biên bản với CĐT.'))
            rec.state = 'cancelled'
