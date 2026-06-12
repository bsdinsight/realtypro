# -*- coding: utf-8 -*-
"""rp.tender.bidder — Nhà thầu nộp HSDT (Phase 5.2).

O2M con từ rp.tender.package. Mỗi nhà thầu nộp hồ sơ dự thầu là 1
record. Quản lý:
- Điểm kỹ thuật (technical_score 0-100, pass threshold 70)
- Giá dự thầu (price_offered)
- Auto-rank theo giá thấp nhất trong cùng gói (qualified bidders)
- Status workflow: submitted → qualified/disqualified → awarded
- action_select_as_winner: copy contractor + price lên package

Chỉ nhà thầu state='approved' (đã duyệt qua master rp.contractor)
mới được tham gia thầu.
"""

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


BIDDER_STATUS = [
    ('submitted', 'Đã nộp HS'),
    ('qualified', 'Đạt vòng KT'),
    ('disqualified', 'Bị loại'),
    ('awarded', 'Trúng thầu'),
]


TECHNICAL_PASS_THRESHOLD = 70.0


class RpTenderBidder(models.Model):
    _name = 'rp.tender.bidder'
    _description = 'Tender Bidder / Nhà thầu nộp HSDT'
    _inherit = ['mail.thread']
    _order = 'package_id, ranking, id'

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

    # ----- Nhà thầu (chỉ approved)
    contractor_id = fields.Many2one(
        'rp.contractor', string='Nhà thầu',
        required=True, ondelete='restrict', tracking=True,
        domain="[('state', '=', 'approved')]",
        help='Chỉ nhà thầu đã được duyệt master (state=approved) '
             'mới được tham gia đấu thầu.',
    )
    partner_id = fields.Many2one(
        related='contractor_id.partner_id', store=True,
        string='Partner',
    )

    # ----- HSDT info
    submitted_date = fields.Date(
        string='Ngày nộp HSDT', tracking=True,
        default=fields.Date.context_today,
    )

    # ----- Đánh giá kỹ thuật
    technical_score = fields.Float(
        string='Điểm KT', digits=(5, 2), tracking=True,
        help=f'Thang 0-100. Pass threshold = {TECHNICAL_PASS_THRESHOLD}.',
    )
    technical_pass = fields.Boolean(
        string='Đạt KT',
        compute='_compute_technical_pass', store=True,
    )

    # ----- Giá dự thầu
    price_offered = fields.Monetary(
        string='Giá dự thầu', tracking=True,
        currency_field='currency_id',
    )

    # ----- Status & ranking
    status = fields.Selection(
        BIDDER_STATUS, string='Trạng thái',
        default='submitted', required=True, tracking=True, copy=False,
    )
    disqualification_reason = fields.Text(
        string='Lý do loại',
    )
    ranking = fields.Integer(
        string='Hạng giá',
        compute='_compute_ranking', store=True,
        help='Xếp hạng theo giá thấp nhất trong cùng gói thầu. '
             'Disqualified bidders bị loại khỏi ranking.',
    )
    is_awarded = fields.Boolean(
        string='Trúng', compute='_compute_is_awarded', store=True,
    )

    notes = fields.Text(string='Ghi chú đánh giá')

    # ===== Computeds =====

    @api.depends('technical_score')
    def _compute_technical_pass(self):
        for b in self:
            b.technical_pass = (
                (b.technical_score or 0) >= TECHNICAL_PASS_THRESHOLD
            )

    @api.depends('package_id.bidder_ids.price_offered',
                 'package_id.bidder_ids.status')
    def _compute_ranking(self):
        """Rank by price ascending; disqualified → ranking = 0."""
        packages = self.mapped('package_id')
        for pkg in packages:
            qualified = pkg.bidder_ids.filtered(
                lambda b: b.status != 'disqualified' and b.price_offered
            ).sorted(key=lambda b: b.price_offered)
            for i, b in enumerate(qualified, start=1):
                b.ranking = i
            rest = pkg.bidder_ids - qualified
            for b in rest:
                b.ranking = 0

    @api.depends('status')
    def _compute_is_awarded(self):
        for b in self:
            b.is_awarded = b.status == 'awarded'

    # ===== Constraints =====

    @api.constrains('technical_score')
    def _check_technical_score_range(self):
        for b in self:
            if b.technical_score and not (0 <= b.technical_score <= 100):
                raise ValidationError(
                    'Điểm KT phải nằm trong khoảng 0-100.')

    @api.constrains('disqualification_reason', 'status')
    def _check_disqualify_reason(self):
        for b in self:
            if b.status == 'disqualified' and not b.disqualification_reason:
                raise ValidationError(
                    'Bidder bị loại cần ghi lý do trong field "Lý do loại".')

    _unique_contractor_per_package = models.Constraint(
        'UNIQUE(package_id, contractor_id)',
        'Mỗi nhà thầu chỉ được nộp 1 HSDT cho 1 gói thầu.',
    )

    # ===== Actions trên bidder =====

    def action_qualify(self):
        """submitted → qualified: đạt vòng đánh giá kỹ thuật."""
        for b in self:
            if b.status == 'awarded':
                raise UserError('Bidder đã trúng thầu — không đổi.')
            if b.status == 'disqualified':
                raise UserError(
                    'Bidder bị loại — reset về submitted trước.')
            if not b.technical_pass:
                raise UserError(
                    f'Điểm KT {b.technical_score} < ngưỡng '
                    f'{TECHNICAL_PASS_THRESHOLD} — không đạt KT.')
            b.status = 'qualified'

    def action_disqualify(self):
        """Loại bidder. Yêu cầu ghi lý do."""
        for b in self:
            if b.status == 'awarded':
                raise UserError(
                    'Bidder đã trúng thầu — không thể loại.')
            if not b.disqualification_reason:
                raise UserError(
                    'Cần ghi lý do loại vào field "Lý do loại" trước.')
            b.status = 'disqualified'

    def action_reset_submitted(self):
        for b in self:
            if b.status == 'awarded':
                raise UserError(
                    'Bidder đã trúng — reset trên package thay vì bidder.')
            b.status = 'submitted'

    def action_select_as_winner(self):
        """Chọn bidder này làm winner.

        - Bidder cũ (status=awarded) → reset về qualified
        - This bidder → awarded
        - Copy contractor + giá lên package
        - Sync contractor.project_ids += package.project_id
        """
        self.ensure_one()
        if self.status == 'disqualified':
            raise UserError('Bidder đã bị loại — không thể chọn trúng.')
        if not self.price_offered:
            raise UserError(
                'Bidder chưa có giá dự thầu — nhập giá rồi mới chọn trúng.')
        if (self.package_id.max_approved_price
                and self.price_offered > self.package_id.max_approved_price):
            raise UserError(
                f'Giá dự thầu ({self.price_offered:,.0f}) vượt giá trần '
                f'duyệt ({self.package_id.max_approved_price:,.0f}).')

        # Reset old winner(s)
        old_winners = self.package_id.bidder_ids.filtered(
            lambda b: b.status == 'awarded' and b.id != self.id)
        old_winners.write({'status': 'qualified'})

        self.status = 'awarded'

        # Copy lên package
        self.package_id.contractor_id = self.contractor_id.partner_id
        self.package_id.award_amount = self.price_offered

        # Sync project relationship trên master nhà thầu
        if self.package_id.project_id not in self.contractor_id.project_ids:
            self.contractor_id.project_ids = [
                (4, self.package_id.project_id.id)]
