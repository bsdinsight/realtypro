# -*- coding: utf-8 -*-
"""IPC — Chứng nhận thanh toán tạm thời (Interim Payment Certificate).

Gom NHIỀU BBNT đã được CĐT duyệt trong một kỳ thành MỘT hồ sơ thanh
toán để trình CĐT ký nhận. Đây là chứng từ pháp lý CĐT ký xác nhận nợ
— khác với BBNT (chỉ xác nhận khối lượng).

Vì sao tách IPC khỏi BBNT: ngân hàng nhận thế chấp theo *chứng từ CĐT
đã ký*, không theo biên bản khối lượng nội bộ. IPC đã ký = quyền đòi
nợ chắc chắn nhất → đưa vào borrowing base được.

Quan hệ: 1 BBNT thuộc TỐI ĐA 1 IPC (`acceptance.ipc_id`) — chặn cứng
việc một khối lượng bị đưa vào hai hồ sơ thanh toán.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class RpOwnerIpc(models.Model):
    _name = 'rp.owner.ipc'
    _description = 'IPC — Chứng nhận thanh toán tạm thời'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_submitted desc, id desc'

    name = fields.Char(
        string='Số IPC', required=True, copy=False,
        default=lambda self: _('/'),
        help='Auto sinh IPC/YYYY/NNNN — sửa được theo số văn bản thực tế.')
    contract_id = fields.Many2one(
        'rp.owner.contract', string='HĐ với CĐT', required=True,
        ondelete='restrict', index=True)
    project_id = fields.Many2one(
        related='contract_id.project_id', store=True, index=True)
    owner_id = fields.Many2one(
        related='contract_id.owner_id', store=True, string='Chủ đầu tư')
    currency_id = fields.Many2one(
        related='contract_id.currency_id', store=True)
    company_id = fields.Many2one(
        related='contract_id.company_id', store=True)

    period_from = fields.Date(string='Kỳ từ ngày')
    period_to = fields.Date(string='Kỳ đến ngày')
    date_submitted = fields.Date(
        string='Ngày trình CĐT', default=fields.Date.context_today,
        tracking=True)

    acceptance_ids = fields.One2many(
        'rp.owner.acceptance', 'ipc_id', string='BBNT trong kỳ',
        help='Chỉ chọn được BBNT đã được CĐT duyệt và CHƯA thuộc IPC khác.')
    acceptance_count = fields.Integer(compute='_compute_amounts')

    # --- Giá trị: cộng từ các BBNT thành viên ---
    amount_gross = fields.Monetary(
        string='Sản lượng gross', compute='_compute_amounts', store=True)
    amount_retention = fields.Monetary(
        string='Giữ lại', compute='_compute_amounts', store=True)
    amount_advance_recovery = fields.Monetary(
        string='Thu hồi tạm ứng', compute='_compute_amounts', store=True)
    amount_backcharge = fields.Monetary(
        string='Back-charge', compute='_compute_amounts', store=True)
    amount_certified = fields.Monetary(
        string='Quyền đòi nợ', compute='_compute_amounts', store=True,
        help='Σ quyền đòi nợ các BBNT — số dùng làm TSBĐ khi CĐT đã ký.')
    amount_net = fields.Monetary(
        string='Đề nghị CĐT thanh toán', compute='_compute_amounts',
        store=True,
        help='Σ tiền CĐT chuyển kỳ này (đã trừ thu hồi tạm ứng).')

    # --- Ký nhận của CĐT ---
    state = fields.Selection(
        [('draft', 'Nháp'),
         ('submitted', 'Đã trình CĐT'),
         ('signed', 'CĐT đã ký nhận'),
         ('cancelled', 'Huỷ')],
        string='Trạng thái', default='draft', required=True, tracking=True)
    date_signed = fields.Date(
        string='Ngày CĐT ký', readonly=True, tracking=True)
    signed_by_id = fields.Many2one(
        'res.partner', string='Người ký bên CĐT', tracking=True,
        domain="['|', ('id', '=', owner_id), ('parent_id', '=', owner_id)]",
        help='Người đại diện CĐT ký nhận — CHỌN từ danh bạ liên hệ của '
             'Chủ đầu tư (không gõ tay, để hồ sơ ngân hàng truy được '
             'đúng pháp nhân/người đại diện).')
    sign_ref = fields.Char(
        string='Số văn bản CĐT ký', tracking=True,
        help='Số công văn/biên bản CĐT xác nhận — chứng từ ngân hàng đòi '
             'xuất trình khi nhận thế chấp quyền đòi nợ.')

    # --- Liên kết tín dụng ---
    # Module này KHÔNG depend re_loan (tránh buộc Community phải có phân
    # hệ vay). Field/nút TSBĐ do `re_loan_borrowing_base` bơm vào qua
    # _inherit; ở đây chỉ để sẵn cờ + hook để workflow chặn đúng.
    is_pledged = fields.Boolean(
        string='Đã đưa vào TSBĐ', compute='_compute_is_pledged', store=True,
        help='IPC đã được gắn làm tài sản bảo đảm cho HĐ tín dụng.')
    amount_pledged = fields.Monetary(
        string='Giá trị đã đem bảo đảm', compute='_compute_is_pledged',
        store=True,
        help='Phần quyền đòi nợ của IPC này NH thực nhận làm bảo đảm — '
             'thường NHỎ HƠN tổng quyền đòi nợ (NH nhận theo tỷ lệ). '
             'Chỉ phần này bị trừ khỏi TSBĐ cấp hợp đồng.')

    note = fields.Text(string='Ghi chú')

    # Odoo 19 BỎ `_sql_constraints` (xem ghi chú ở rp.owner.contract).
    # IPC là chứng từ trình CĐT thanh toán — trùng số là vấn đề hồ sơ.
    _name_company_unique = models.Constraint(
        'unique(name, company_id)', 'Số IPC đã tồn tại.')

    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _('/'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'rp.owner.ipc') or _('/')
        return super().create(vals_list)

    @api.depends('acceptance_ids.amount_this_period',
                 'acceptance_ids.retention_amount',
                 'acceptance_ids.advance_recovery',
                 'acceptance_ids.backcharge',
                 'acceptance_ids.amount_certified',
                 'acceptance_ids.amount_net')
    def _compute_amounts(self):
        for rec in self:
            acc = rec.acceptance_ids
            rec.acceptance_count = len(acc)
            rec.amount_gross = sum(acc.mapped('amount_this_period'))
            rec.amount_retention = sum(acc.mapped('retention_amount'))
            rec.amount_advance_recovery = sum(acc.mapped('advance_recovery'))
            rec.amount_backcharge = sum(acc.mapped('backcharge'))
            rec.amount_certified = sum(acc.mapped('amount_certified'))
            rec.amount_net = sum(acc.mapped('amount_net'))

    def _compute_is_pledged(self):
        """Mặc định KHÔNG có phân hệ vay → không bao giờ bị cầm cố.
        `re_loan_borrowing_base` override để tính theo TSBĐ thật."""
        for rec in self:
            rec.is_pledged = False
            rec.amount_pledged = 0.0

    @api.constrains('acceptance_ids', 'contract_id')
    def _check_acceptances(self):
        for rec in self:
            for a in rec.acceptance_ids:
                if a.contract_id != rec.contract_id:
                    raise ValidationError(_(
                        'BBNT %(a)s thuộc HĐ khác (%(c)s) — không đưa vào '
                        'IPC của HĐ %(h)s được.',
                        a=a.name, c=a.contract_id.name,
                        h=rec.contract_id.name))
                if a.state != 'approved':
                    raise ValidationError(_(
                        'BBNT %(a)s chưa được CĐT duyệt (đang %(s)s) — '
                        'chỉ gom BBNT đã duyệt vào IPC.',
                        a=a.name, s=a.state))

    # ------------------------------------------------------------------
    # Workflow ký nhận
    # ------------------------------------------------------------------
    def action_submit(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Chỉ IPC Nháp mới trình CĐT được.'))
            if not rec.acceptance_ids:
                raise UserError(_(
                    'IPC %s chưa có BBNT nào — chọn BBNT đã duyệt trước '
                    'khi trình CĐT.', rec.name))
            rec.state = 'submitted'
            rec.message_post(body=_(
                'Trình CĐT IPC %(n)s — %(c)s BBNT, đề nghị thanh toán '
                '%(a)s (quyền đòi nợ %(q)s).',
                n=rec.name, c=len(rec.acceptance_ids),
                a='{:,.0f}'.format(rec.amount_net),
                q='{:,.0f}'.format(rec.amount_certified)))

    def action_sign(self):
        """CĐT ký nhận — từ đây IPC đủ điều kiện làm TSBĐ."""
        for rec in self:
            if rec.state != 'submitted':
                raise UserError(_(
                    'Chỉ IPC Đã trình CĐT mới ghi nhận ký nhận được.'))
            if not rec.signed_by_id or not rec.sign_ref:
                raise UserError(_(
                    'Nhập "Người ký bên CĐT" và "Số văn bản CĐT ký" trước '
                    'khi xác nhận — đây là chứng từ ngân hàng yêu cầu khi '
                    'nhận thế chấp quyền đòi nợ.'))
            rec.state = 'signed'
            rec.date_signed = fields.Date.context_today(rec)
            rec.message_post(body=_(
                'CĐT ký nhận IPC %(n)s — %(p)s ký, văn bản %(r)s. '
                'Quyền đòi nợ <b>%(q)s</b> đủ điều kiện làm TSBĐ.',
                n=rec.name, p=rec.signed_by_id.display_name,
                r=rec.sign_ref,
                q='{:,.0f}'.format(rec.amount_certified)))

    def action_reset_draft(self):
        for rec in self:
            if rec.state == 'signed' and rec.is_pledged:
                raise UserError(_(
                    'IPC %s đang là TSBĐ của HĐ tín dụng — giải chấp '
                    'trước khi mở lại.', rec.name))
            rec.state = 'draft'

    def action_cancel(self):
        for rec in self:
            if rec.is_pledged:
                raise UserError(_(
                    'IPC %s đang là TSBĐ — giải chấp trước khi huỷ.',
                    rec.name))
            rec.state = 'cancelled'

    # ------------------------------------------------------------------
    def _check_can_pledge(self):
        """Điều kiện đưa IPC vào TSBĐ — dùng chung cho nút & wizard."""
        self.ensure_one()
        if self.state != 'signed':
            raise UserError(_(
                'Chỉ IPC CĐT ĐÃ KÝ NHẬN mới đưa vào TSBĐ được. IPC %(n)s '
                'đang ở trạng thái "%(s)s".',
                n=self.name, s=dict(
                    self._fields['state'].selection)[self.state]))
        if self.amount_certified <= 0:
            raise UserError(_(
                'IPC %s có quyền đòi nợ = 0 — không làm TSBĐ được.',
                self.name))

    def action_apply_to_credit(self):
        """Đưa IPC vào HĐ tín dụng — `re_loan_borrowing_base` override."""
        self.ensure_one()
        self._check_can_pledge()
        raise UserError(_(
            'Chưa cài phân hệ Vay & Borrowing base (re_loan_borrowing_base) '
            '— không đưa IPC vào hợp đồng tín dụng được.'))

    # ------------------------------------------------------------------
    # Gom BBNT
    # ------------------------------------------------------------------
    def _domain_gatherable_acceptances(self):
        """BBNT đủ điều kiện gom: cùng HĐ · ĐÃ CĐT DUYỆT · CHƯA thuộc IPC nào.

        Không cho gõ tay thêm dòng ở bảng BBNT — khối lượng phải đi từ BBNT
        có thật, đã duyệt. Đây là chỗ chặn 'một khối lượng vào hai hồ sơ'.
        """
        self.ensure_one()
        dom = [
            ('contract_id', '=', self.contract_id.id),
            ('state', '=', 'approved'),
            ('ipc_id', '=', False),
        ]
        # nếu có khai kỳ thì chỉ gom BBNT duyệt trong kỳ
        if self.period_from:
            dom.append(('date_approved', '>=', self.period_from))
        if self.period_to:
            dom.append(('date_approved', '<=', self.period_to))
        return dom

    def action_gather_acceptances(self):
        """Kéo mọi BBNT đủ điều kiện vào IPC này."""
        self.ensure_one()
        if self.state == 'signed':
            raise UserError(_('IPC đã được CĐT ký nhận — không gom thêm BBNT.'))
        if not self.contract_id:
            raise UserError(_('Chọn Hợp đồng với CĐT trước khi gom BBNT.'))
        Acc = self.env['rp.owner.acceptance']
        found = Acc.search(self._domain_gatherable_acceptances())
        if not found:
            msg = _('Không có BBNT nào đủ điều kiện '
                    '(đã CĐT duyệt · chưa thuộc IPC khác'
                    '%s).') % (_(' · duyệt trong kỳ')
                               if (self.period_from or self.period_to) else '')
        else:
            found.write({'ipc_id': self.id})
            msg = _('Đã gom %s BBNT vào IPC.') % len(found)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Gom BBNT'),
                'message': msg,
                'type': 'success' if found else 'warning',
                'sticky': False,
            },
        }
