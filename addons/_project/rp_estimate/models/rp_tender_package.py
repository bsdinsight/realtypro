# -*- coding: utf-8 -*-
"""rp.tender.package — Gói thầu (Phase 5.1 — kế hoạch lựa chọn NT).

Phase 5.1 ships:
- Header: name, code, project, currency, scope, contractor (existing)
- Plan fields: selection_method, deadline_contract, 6 mốc thời gian
  kế hoạch lựa chọn nhà thầu, max_approved_price, award_amount,
  contract_amount
- State machine 8-step: draft → approved → inviting → bid_closed →
  evaluating → negotiating → awarded → contracted → closed (+cancelled)
- Lines (existing): rp.structure picker per package line

Phase 5.2 (sau): Bidder list + chấm điểm + auto-rank + award
Phase 5.3 (sau): Tiêu chuẩn đánh giá + scope HTML + attachments
Phase 5.4 (sau): action_contract auto-tạo rp.contract draft
"""

from odoo import api, fields, models
from odoo.exceptions import ValidationError, UserError


SELECTION_METHODS = [
    ('open', 'Đấu thầu rộng rãi'),
    ('restricted', 'Đấu thầu hạn chế'),
    ('designated', 'Chỉ định thầu'),
    ('direct', 'Mua sắm trực tiếp'),
    ('competitive_offer', 'Chào hàng cạnh tranh'),
    ('epc', 'EPC / Tổng thầu'),
    ('self_perform', 'Tự thực hiện'),
]


TENDER_STATES = [
    ('draft', 'Nháp'),
    ('approved', 'Đã duyệt KH'),
    ('inviting', 'Đang mời thầu'),
    ('bid_closed', 'Đã đóng thầu'),
    ('evaluating', 'Đang đánh giá'),
    ('negotiating', 'Đang thương thảo'),
    ('awarded', 'Đã có KQ'),
    ('contracted', 'Đã ký HĐ'),
    ('closed', 'Đã đóng gói thầu'),
    ('cancelled', 'Đã hủy'),
]


class RpTenderPackage(models.Model):
    _name = 'rp.tender.package'
    _description = 'Tender Package / Gói thầu'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'project_id, sequence, code, id desc'

    # ----- Identity
    name = fields.Char(
        string='Tên gói thầu',
        required=True, translate=True, tracking=True,
    )
    code = fields.Char(string='Mã gói thầu', tracking=True)
    sequence = fields.Integer(default=10)

    # ----- Project anchor
    project_id = fields.Many2one(
        're.project', string='Dự án',
        required=True, ondelete='restrict', index=True, tracking=True,
    )

    # ----- Subzone filter (UX)
    subzone_filter_id = fields.Many2one(
        're.subzone', string='Lọc theo khu vực',
        domain="[('project_id', '=', project_id)]",
        help='UX convenience: filter khi add Hạng mục — không restrict.',
    )

    # ----- Contractor (awarded — set sau khi award)
    contractor_id = fields.Many2one(
        'res.partner', string='Nhà thầu trúng',
        ondelete='set null', tracking=True,
        domain="[('is_company', '=', True)]",
        help='Nhà thầu trúng — set sau khi award.',
    )

    # ----- Scope
    scope_summary = fields.Text(
        string='Phạm vi gói thầu',
        help='Mô tả phạm vi dùng cho HSMT / RFP.',
    )

    # ===== Phase 5.1: Kế hoạch lựa chọn nhà thầu =====

    selection_method = fields.Selection(
        SELECTION_METHODS,
        string='Hình thức lựa chọn nhà thầu', tracking=True,
    )
    deadline_contract = fields.Date(
        string='Hạn ký HĐ (PTDA giao)', tracking=True,
        help='Hạn cuối bộ phận đấu thầu phải hoàn tất đấu thầu và ký '
             'được HĐ. Do PTDA giao khi lập kế hoạch dự án.',
    )

    # 6 mốc thời gian kế hoạch lựa chọn nhà thầu
    date_rfp_issue = fields.Date(
        string='Ngày phát hành HSMT', tracking=True,
        help='Hồ sơ mời thầu (HSMT) phát hành ra nhà thầu.',
    )
    date_bid_close = fields.Date(
        string='Ngày đóng thầu', tracking=True,
        help='Hạn cuối nhận hồ sơ dự thầu (HSDT).',
    )
    date_bid_open = fields.Date(
        string='Ngày mở thầu', tracking=True,
        help='Ngày tổ chức mở thầu công khai.',
    )
    date_eval_done = fields.Date(
        string='Ngày hoàn tất đánh giá', tracking=True,
    )
    date_negotiation_done = fields.Date(
        string='Ngày hoàn tất thương thảo', tracking=True,
    )
    date_award_signed = fields.Date(
        string='Ngày phê duyệt + ký HĐ', tracking=True,
        help='Ngày phê duyệt KQ lựa chọn nhà thầu và ký HĐ.',
    )

    # Giá trị tài chính
    estimated_amount = fields.Monetary(
        string='Giá trị ước tính',
        currency_field='currency_id',
    )
    max_approved_price = fields.Monetary(
        string='Giá trần duyệt', tracking=True,
        currency_field='currency_id',
        help='Giá tối đa của gói thầu đã được phê duyệt.',
    )
    award_amount = fields.Monetary(
        string='Giá trúng thầu', tracking=True,
        currency_field='currency_id',
        help='Giá trúng thầu sau khi xét trúng.',
    )
    contract_amount = fields.Monetary(
        string='Giá trị HĐ ký', tracking=True,
        currency_field='currency_id',
        help='Giá trị HĐ ký kết — có thể khác giá trúng nếu thương thảo.',
    )

    # ----- Cảnh báo deadline
    days_to_deadline = fields.Integer(
        compute='_compute_deadline_status', store=True,
        help='Số ngày còn lại tới hạn ký HĐ (âm = quá hạn).',
    )
    is_deadline_overdue = fields.Boolean(
        compute='_compute_deadline_status', store=True,
    )

    # Note: contract_id (M2O → rp.contract) sẽ được Phase 5.4 thêm
    # qua bridge module rp_contract_tender — rp_estimate không depend
    # rp_contract để tránh upgrade chain.

    currency_id = fields.Many2one(
        'res.currency', string='Currency',
        required=True, default=lambda self: self.env.company.currency_id,
    )

    # ----- Lines (Hạng mục)
    line_ids = fields.One2many(
        'rp.tender.package.line', 'package_id',
        string='Hạng mục in Package', copy=True,
    )
    line_count = fields.Integer(compute='_compute_line_count', store=True)

    # ----- Bidders (Phase 5.2)
    bidder_ids = fields.One2many(
        'rp.tender.bidder', 'package_id',
        string='Nhà thầu nộp HSDT', copy=False,
    )
    bidder_count = fields.Integer(
        compute='_compute_bidder_stats', store=True,
    )
    bidder_qualified_count = fields.Integer(
        compute='_compute_bidder_stats', store=True,
        help='Số bidder đạt vòng KT.',
    )
    awarded_bidder_id = fields.Many2one(
        'rp.tender.bidder',
        string='Bidder trúng thầu',
        compute='_compute_awarded_bidder', store=True,
    )
    subzone_coverage = fields.Char(
        compute='_compute_subzone_coverage', store=True,
        help='Subzones covered by package lines.',
    )

    # ----- State 8-step (+ cancelled)
    state = fields.Selection(
        TENDER_STATES,
        string='Trạng thái', default='draft', required=True,
        tracking=True, readonly=True, copy=False,
    )

    # ----- Misc
    description = fields.Text()
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', string='Company',
        default=lambda self: self.env.company,
    )

    # ===== Onchange =====

    @api.onchange('contractor_id')
    def _onchange_contractor_flag(self):
        if self.contractor_id and not self.contractor_id.is_contractor:
            self.contractor_id.is_contractor = True

    @api.onchange('award_amount')
    def _onchange_award_default_contract(self):
        """Gợi ý contract_amount = award_amount nếu chưa nhập."""
        if self.award_amount and not self.contract_amount:
            self.contract_amount = self.award_amount

    # ===== Computeds =====

    @api.depends('line_ids')
    def _compute_line_count(self):
        for pkg in self:
            pkg.line_count = len(pkg.line_ids)

    @api.depends('bidder_ids', 'bidder_ids.status')
    def _compute_bidder_stats(self):
        for pkg in self:
            pkg.bidder_count = len(pkg.bidder_ids)
            pkg.bidder_qualified_count = len(pkg.bidder_ids.filtered(
                lambda b: b.status in ('qualified', 'awarded')))

    @api.depends('bidder_ids.status')
    def _compute_awarded_bidder(self):
        for pkg in self:
            awarded = pkg.bidder_ids.filtered(
                lambda b: b.status == 'awarded')
            pkg.awarded_bidder_id = awarded[:1]

    @api.depends('line_ids.subzone_id')
    def _compute_subzone_coverage(self):
        for pkg in self:
            subzones = pkg.line_ids.mapped('subzone_id')
            if not subzones:
                pkg.subzone_coverage = ''
                continue
            names = sorted(set(sz.name for sz in subzones if sz))
            pkg.subzone_coverage = ', '.join(names) if names \
                else 'Common Cost only'

    @api.depends('deadline_contract', 'state')
    def _compute_deadline_status(self):
        today = fields.Date.context_today(self)
        for pkg in self:
            if (not pkg.deadline_contract
                    or pkg.state in ('contracted', 'closed', 'cancelled')):
                pkg.days_to_deadline = 0
                pkg.is_deadline_overdue = False
                continue
            delta = (pkg.deadline_contract - today).days
            pkg.days_to_deadline = delta
            pkg.is_deadline_overdue = delta < 0

    # ===== Constraints =====

    def init(self):
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS rp_tender_package_unique_code_per_project
            ON rp_tender_package (project_id, code)
            WHERE code IS NOT NULL
        """)

    @api.constrains('contractor_id', 'company_id')
    def _check_contractor_company(self):
        for pkg in self:
            if (pkg.contractor_id
                    and pkg.contractor_id.company_id != pkg.company_id):
                raise ValidationError(
                    'Nhà thầu phải cùng company với gói thầu.')

    @api.constrains(
        'date_rfp_issue', 'date_bid_close', 'date_bid_open',
        'date_eval_done', 'date_negotiation_done', 'date_award_signed',
        'deadline_contract',
    )
    def _check_timeline_order(self):
        """Các mốc thời gian phải tăng dần.

        Cho phép null — chỉ check khi cả 2 mốc liền nhau đều có giá trị.
        Cuối cùng date_award_signed phải <= deadline_contract.
        """
        sequence = [
            ('date_rfp_issue', 'Ngày phát hành HSMT'),
            ('date_bid_close', 'Ngày đóng thầu'),
            ('date_bid_open', 'Ngày mở thầu'),
            ('date_eval_done', 'Ngày hoàn tất đánh giá'),
            ('date_negotiation_done', 'Ngày hoàn tất thương thảo'),
            ('date_award_signed', 'Ngày phê duyệt + ký HĐ'),
        ]
        for pkg in self:
            prev_name = None
            prev_val = None
            for fname, flabel in sequence:
                val = pkg[fname]
                if val and prev_val and val < prev_val:
                    raise ValidationError(
                        f'{flabel} ({val}) phải >= {prev_name} '
                        f'({prev_val}).')
                if val:
                    prev_name, prev_val = flabel, val
            if (pkg.date_award_signed and pkg.deadline_contract
                    and pkg.date_award_signed > pkg.deadline_contract):
                raise ValidationError(
                    f'Ngày ký HĐ ({pkg.date_award_signed}) vượt hạn '
                    f'PTDA giao ({pkg.deadline_contract}).')

    # ===== State transitions =====

    def _require_fields(self, fields_map):
        """Helper: validate required fields, raise UserError với list."""
        missing = [label for fname, label in fields_map.items()
                   if not self[fname]]
        if missing:
            raise UserError(
                'Cần điền các trường sau: ' + ', '.join(missing))

    def action_approve_plan(self):
        """draft → approved: duyệt kế hoạch lựa chọn nhà thầu."""
        for pkg in self:
            if pkg.state != 'draft':
                continue
            if not pkg.line_ids:
                raise UserError(
                    'Không thể duyệt gói thầu không có Hạng mục nào.')
            pkg._require_fields({
                'selection_method': 'Hình thức lựa chọn nhà thầu',
                'deadline_contract': 'Hạn ký HĐ',
                'max_approved_price': 'Giá trần duyệt',
            })
            pkg.state = 'approved'

    def action_invite(self):
        """approved → inviting: bắt đầu phát hành HSMT."""
        today = fields.Date.context_today(self)
        for pkg in self:
            if pkg.state != 'approved':
                continue
            if not pkg.date_rfp_issue:
                pkg.date_rfp_issue = today
            pkg.state = 'inviting'

    def action_close_bid(self):
        """inviting → bid_closed: đóng thầu, không nhận HSDT mới."""
        today = fields.Date.context_today(self)
        for pkg in self:
            if pkg.state != 'inviting':
                continue
            if not pkg.date_bid_close:
                pkg.date_bid_close = today
            pkg.state = 'bid_closed'

    def action_evaluate(self):
        """bid_closed → evaluating: mở thầu + bắt đầu đánh giá."""
        today = fields.Date.context_today(self)
        for pkg in self:
            if pkg.state != 'bid_closed':
                continue
            if not pkg.date_bid_open:
                pkg.date_bid_open = today
            pkg.state = 'evaluating'

    def action_negotiate(self):
        """evaluating → negotiating: chấm xong, vào thương thảo."""
        today = fields.Date.context_today(self)
        for pkg in self:
            if pkg.state != 'evaluating':
                continue
            if not pkg.date_eval_done:
                pkg.date_eval_done = today
            pkg.state = 'negotiating'

    def action_award(self):
        """negotiating → awarded: chốt nhà thầu trúng + giá trúng.

        2 flow chấp nhận:
        - User đã click "Chọn trúng" trên 1 bidder → awarded_bidder_id
          đã set → contractor_id + award_amount đã sync tự động
        - Hoặc user nhập tay contractor_id + award_amount (vd chỉ định
          thầu không có bidder list)
        """
        today = fields.Date.context_today(self)
        for pkg in self:
            if pkg.state != 'negotiating':
                continue

            if pkg.bidder_ids and not pkg.awarded_bidder_id:
                raise UserError(
                    'Có bidder trong gói thầu — phải chọn "Trúng" trên '
                    '1 bidder ở tab Danh sách nhà thầu trước khi award.')

            pkg._require_fields({
                'contractor_id': 'Nhà thầu trúng',
                'award_amount': 'Giá trúng thầu',
            })
            if pkg.award_amount > pkg.max_approved_price:
                raise UserError(
                    f'Giá trúng ({pkg.award_amount}) vượt giá trần duyệt '
                    f'({pkg.max_approved_price}).')

            # Sync project relationship trên contractor master (cho cả
            # trường hợp pick contractor tay không qua bidder)
            if pkg.contractor_id:
                contractor = self.env['rp.contractor'].search(
                    [('partner_id', '=', pkg.contractor_id.id)], limit=1)
                if (contractor
                        and pkg.project_id not in contractor.project_ids):
                    contractor.project_ids = [(4, pkg.project_id.id)]

            if not pkg.date_negotiation_done:
                pkg.date_negotiation_done = today
            pkg.state = 'awarded'

    def action_contract(self):
        """awarded → contracted: ký HĐ.

        Phase 5.4 sẽ override: auto-tạo rp.contract draft + set
        contract_id. P5.1 chỉ set state + ngày ký.
        """
        today = fields.Date.context_today(self)
        for pkg in self:
            if pkg.state != 'awarded':
                continue
            pkg._require_fields({
                'contract_amount': 'Giá trị HĐ ký',
            })
            if not pkg.date_award_signed:
                pkg.date_award_signed = today
            pkg.state = 'contracted'

    def action_close(self):
        """contracted → closed: đóng gói thầu (sau khi HĐ hoàn tất)."""
        for pkg in self:
            if pkg.state != 'contracted':
                continue
            pkg.state = 'closed'

    def action_cancel(self):
        """Bất cứ state nào → cancelled."""
        for pkg in self:
            if pkg.state in ('closed', 'cancelled'):
                continue
            pkg.state = 'cancelled'

    def action_reset_to_draft(self):
        if not self.env.user.has_group('re_base.group_re_manager'):
            raise UserError('Chỉ manager mới được reset state.')
        for pkg in self:
            pkg.state = 'draft'

    def action_open_bidders(self):
        """Mở danh sách bidder của gói thầu (cho stat button)."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Nhà thầu nộp HSDT — {self.name}',
            'res_model': 'rp.tender.bidder',
            'view_mode': 'list,form',
            'domain': [('package_id', '=', self.id)],
            'context': {
                'default_package_id': self.id,
                'search_default_group_status': 1,
            },
        }


class RpTenderPackageLine(models.Model):
    _name = 'rp.tender.package.line'
    _description = 'Tender Package Line'
    _order = 'package_id, sequence, id'

    package_id = fields.Many2one(
        'rp.tender.package', string='Gói thầu',
        required=True, ondelete='cascade', index=True,
    )
    project_id = fields.Many2one(
        related='package_id.project_id', store=True, index=True,
    )
    currency_id = fields.Many2one(
        related='package_id.currency_id', store=True,
    )

    sequence = fields.Integer(default=10)
    name = fields.Char(
        string='Mô tả',
        translate=True,
        help='Optional override. If empty, displays structure name.',
    )

    # ----- Anchor
    structure_id = fields.Many2one(
        'rp.structure', string='Hạng mục',
        required=True, ondelete='restrict', index=True,
    )
    subzone_id = fields.Many2one(
        're.subzone', string='Khu vực',
        related='structure_id.subzone_id', store=True,
        index=True, readonly=True,
    )
    structure_level = fields.Selection(
        related='structure_id.structure_level', store=True, readonly=True,
    )
    structure_type = fields.Selection(
        related='structure_id.structure_type', store=True, readonly=True,
    )

    # ----- Amount
    estimated_amount = fields.Monetary(
        string='Giá trị ước tính',
        currency_field='currency_id',
    )

    # ----- Note
    scope_note = fields.Text(string='Ghi chú phạm vi')

    @api.constrains('structure_id', 'package_id')
    def _check_structure_same_project(self):
        for line in self:
            if line.structure_id.project_id != line.package_id.project_id:
                raise ValidationError(
                    'Hạng mục phải cùng dự án với gói thầu.')

    _unique_structure_per_package = models.Constraint(
        'UNIQUE(package_id, structure_id)',
        'Mỗi Hạng mục chỉ có thể xuất hiện một lần trong gói thầu.',
    )
