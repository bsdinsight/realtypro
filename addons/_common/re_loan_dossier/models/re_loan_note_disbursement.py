# -*- coding: utf-8 -*-
"""Giải ngân: danh sách hồ sơ + điều kiện gửi ngân hàng."""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ReLoanNoteDisbursement(models.Model):
    _inherit = 're.loan.note.disbursement'

    dossier_line_ids = fields.One2many(
        'rp.loan.disbursement.dossier', 'disbursement_id',
        string='Hồ sơ giải ngân')
    dossier_count = fields.Integer(compute='_compute_dossier_stats')
    dossier_total = fields.Monetary(
        string='Σ giá trị hồ sơ',
        compute='_compute_dossier_stats', store=True,
        help='Tổng giá trị các hồ sơ — phải bằng số tiền giải ngân.')
    dossier_balance = fields.Monetary(
        string='Chênh lệch',
        compute='_compute_dossier_stats', store=True,
        help='= Số tiền giải ngân − Σ hồ sơ. Phải bằng 0 khi gửi NH.')

    @api.depends('dossier_line_ids', 'dossier_line_ids.amount', 'amount')
    def _compute_dossier_stats(self):
        for rec in self:
            rec.dossier_count = len(rec.dossier_line_ids)
            rec.dossier_total = sum(rec.dossier_line_ids.mapped('amount'))
            rec.dossier_balance = rec.amount - rec.dossier_total

    @api.onchange('dossier_line_ids')
    def _onchange_dossier_sum_amount(self):
        """Sửa danh sách hồ sơ thì số tiền giải ngân tự bằng Σ hồ sơ —
        để chênh lệch luôn về 0. Vẫn sửa tay đè được."""
        if self.dossier_line_ids:
            self.amount = sum(self.dossier_line_ids.mapped('amount'))

    def _check_ready_to_submit(self):
        super()._check_ready_to_submit()
        for rec in self:
            if not rec.dossier_line_ids:
                raise UserError(_(
                    'Cần ít nhất 1 hồ sơ giải ngân trước khi gửi NH.'))
            # Hồ sơ loại Tạm ứng KHÔNG có hoá đơn — đó là cả lý do nó
            # tồn tại: trả trước cho nhà thầu thì chưa ai xuất hoá đơn
            # (việc 1432). Chỉ hồ sơ loại Hoá đơn mới bắt.
            missing_inv = rec.dossier_line_ids.filtered(
                lambda d: d.dossier_kind == 'invoice' and not d.invoice_id)
            if missing_inv:
                raise UserError(_(
                    '%(n)s hồ sơ thiếu Hóa đơn. NH yêu cầu mỗi hồ sơ '
                    'phải có hoá đơn của nhà thầu — nếu đây là tiền '
                    'trả trước khi có hoá đơn, đổi "Loại hồ sơ" sang '
                    'Tạm ứng.',
                    n=len(missing_inv)))
            missing_adv = rec.dossier_line_ids.filtered(
                lambda d: d.dossier_kind == 'advance'
                and not d.advance_partner_id)
            if missing_adv:
                raise UserError(_(
                    '%(n)s hồ sơ tạm ứng chưa khai Bên nhận tạm ứng. '
                    'NH cần biết tiền đi đâu.',
                    n=len(missing_adv)))
            # Dung sai 1đ cho làm tròn VND.
            if abs(rec.dossier_balance) > 1:
                raise UserError(_(
                    'Σ giá trị hồ sơ (%(d)s) khác số tiền giải ngân '
                    '(%(a)s). Chênh lệch: %(b)s. Điều chỉnh cho khớp '
                    'trước khi gửi NH.',
                    d=rec.dossier_total, a=rec.amount,
                    b=rec.dossier_balance))
