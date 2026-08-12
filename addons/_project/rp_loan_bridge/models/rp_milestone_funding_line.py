# -*- coding: utf-8 -*-
"""Phân bổ NHIỀU NGUỒN cho một mốc thanh toán HĐ nhà thầu.

Anh Đại 2026-08-11: một hoá đơn/mốc có thể trả bằng hai nguồn — ví dụ
một phần lấy từ tạm ứng CĐT, phần còn lại giải ngân từ khế ước vay.

Cách dùng:
- Mốc chỉ có MỘT nguồn → khai thẳng ô "Nguồn chi trả" như cũ, khỏi tạo
  dòng nào (đa số trường hợp).
- Mốc chia nhiều nguồn → thêm dòng ở đây. Khi đã có dòng thì **dòng
  thắng**, ô "Nguồn chi trả" chỉ còn là nhãn hiển thị 'Nhiều nguồn'.

Số tiền rút từ tạm ứng CĐT (dù khai kiểu nào) đều trừ vào tiền còn lại
của đúng đợt tạm ứng đó.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

FUNDING_SOURCES = [
    ('equity', 'Vốn tự có'),
    ('owner_advance', 'Tạm ứng CĐT'),
    ('loan', 'Khế ước vay'),
]


class RpMilestoneFundingLine(models.Model):
    _name = 'rp.milestone.funding.line'
    _description = 'Phân bổ nguồn chi trả cho mốc thanh toán'
    _order = 'milestone_id, id'

    milestone_id = fields.Many2one(
        'rp.contract.payment.milestone', string='Mốc thanh toán',
        required=True, ondelete='cascade', index=True)
    contract_id = fields.Many2one(
        related='milestone_id.contract_id', string='HĐ nhà thầu',
        store=True, readonly=True)
    project_id = fields.Many2one(
        related='milestone_id.contract_id.project_id', string='Dự án',
        store=True, readonly=True)
    currency_id = fields.Many2one(
        related='milestone_id.currency_id', readonly=True)

    source = fields.Selection(
        FUNDING_SOURCES, string='Nguồn', required=True, default='loan')
    owner_advance_id = fields.Many2one(
        'rp.owner.advance', string='Đợt tạm ứng CĐT',
        help='Bắt buộc khi nguồn = Tạm ứng CĐT.')
    loan_note_id = fields.Many2one(
        're.loan.note', string='Khế ước (KW)',
        help='Bắt buộc khi nguồn = Khế ước vay.')
    amount = fields.Monetary(string='Số tiền', required=True)
    note = fields.Char(string='Diễn giải')

    @api.onchange('source')
    def _onchange_source_clear(self):
        if self.source != 'owner_advance':
            self.owner_advance_id = False
        if self.source != 'loan':
            self.loan_note_id = False

    @api.constrains('amount', 'milestone_id')
    def _check_parent_total(self):
        """Constraint trên o2m của CHA không fire khi tạo dòng trực tiếp
        → phải gọi lại từ phía CON (bẫy Odoo đã dính ở bảng phân bổ hạn
        mức trước đây)."""
        self.mapped('milestone_id')._check_split_not_over()

    @api.constrains('source', 'owner_advance_id', 'amount')
    def _check_line(self):
        for ln in self:
            if ln.amount <= 0:
                raise ValidationError(_('Số tiền phân bổ phải lớn hơn 0.'))
            if ln.source == 'owner_advance' and not ln.owner_advance_id:
                raise ValidationError(_(
                    'Dòng nguồn "Tạm ứng CĐT" phải chọn đợt tạm ứng.'))
            adv = ln.owner_advance_id
            if adv and adv.owner_contract_id.project_id != ln.project_id:
                raise ValidationError(_(
                    'Đợt tạm ứng %(a)s thuộc dự án khác với mốc thanh '
                    'toán.', a=adv.name))


class RpContractPaymentMilestoneSplit(models.Model):
    _inherit = 'rp.contract.payment.milestone'

    funding_line_ids = fields.One2many(
        'rp.milestone.funding.line', 'milestone_id',
        string='Phân bổ nhiều nguồn')
    funding_split_total = fields.Monetary(
        string='Σ đã phân bổ nguồn', compute='_compute_funding_split')
    funding_unallocated = fields.Monetary(
        string='Chưa gán nguồn', compute='_compute_funding_split',
        help='= Số tiền mốc − Σ đã phân bổ. Phải về 0 khi dùng chia '
             'nhiều nguồn.')
    is_split_funding = fields.Boolean(
        string='Chia nhiều nguồn', compute='_compute_funding_split')
    # KHÔNG store: chỉ dùng cho readonly/invisible trên view. Trộn field
    # lưu và không lưu trong CÙNG một compute khiến Odoo cảnh báo "đọc
    # field này có thể GHI field kia" — tức mở form cũng sinh ghi DB.

    @api.depends('funding_line_ids.amount', 'amount')
    def _compute_funding_split(self):
        for rec in self:
            total = sum(rec.funding_line_ids.mapped('amount'))
            rec.funding_split_total = total
            rec.funding_unallocated = (rec.amount or 0.0) - total
            rec.is_split_funding = bool(rec.funding_line_ids)

    @api.constrains('funding_line_ids', 'amount')
    def _check_split_not_over(self):
        for rec in self:
            if not rec.funding_line_ids:
                continue
            total = sum(rec.funding_line_ids.mapped('amount'))
            if total > (rec.amount or 0.0) + 0.01:
                raise ValidationError(_(
                    "Mốc '%(m)s': Σ phân bổ nguồn (%(t)s) vượt số tiền "
                    "mốc (%(a)s).",
                    m=rec.name, t='{:,.0f}'.format(total),
                    a='{:,.0f}'.format(rec.amount or 0.0)))

    def _amount_from_source(self, source, advance=None):
        """Số tiền mốc này lấy từ `source` (và từ đúng đợt tạm ứng nếu có).

        Có dòng phân bổ thì DÒNG THẮNG; không có thì cả mốc tính về ô
        "Nguồn chi trả".
        """
        self.ensure_one()
        if self.funding_line_ids:
            lines = self.funding_line_ids.filtered(
                lambda l: l.source == source)
            if advance is not None:
                lines = lines.filtered(lambda l: l.owner_advance_id == advance)
            return sum(lines.mapped('amount'))
        if self.funding_source != source:
            return 0.0
        if advance is not None and self.owner_advance_id != advance:
            return 0.0
        return self.amount or 0.0
