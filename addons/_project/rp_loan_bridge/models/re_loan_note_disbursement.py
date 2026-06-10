# -*- coding: utf-8 -*-
"""Bridge: thêm cost_category_id + contract_id (rp.contract) cho disbursement.

Phase 2: thêm dossier_line_ids (hồ sơ giải ngân = BBN + Hóa đơn) và
override _check_ready_to_submit để bắt buộc có hồ sơ đầy đủ.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ReLoanNoteDisbursement(models.Model):
    _inherit = 're.loan.note.disbursement'

    cost_category_id = fields.Many2one(
        'rp.cost.category', string='Nhóm chi phí',
        domain="[('project_id', '=', project_id)]",
        help='Loại chi phí của khoản chi (rp.cost.category của dự án).')
    contract_id = fields.Many2one(
        'rp.contract', string='HĐ nhà thầu',
        domain="[('project_id', '=', project_id)]",
        help='HĐ nhà thầu được thanh toán bằng khoản giải ngân này '
             '(nếu giải ngân để trả nhà thầu).')
    structure_id = fields.Many2one(
        'rp.structure', string='Hạng mục',
        domain="[('project_id', '=', project_id)]",
        help='Hạng mục công trình (nếu cần theo dõi chi tiết hơn).')

    # --- Hồ sơ giải ngân (BBN + Hóa đơn) ---
    dossier_line_ids = fields.One2many(
        'rp.loan.disbursement.dossier', 'disbursement_id',
        string='Hồ sơ giải ngân')
    dossier_count = fields.Integer(
        compute='_compute_dossier_stats')
    dossier_total = fields.Monetary(
        string='Σ giá trị hồ sơ',
        compute='_compute_dossier_stats', store=True,
        help='Tổng giá trị các hồ sơ giải ngân — phải = số tiền GN.')
    dossier_balance = fields.Monetary(
        string='Chênh lệch',
        compute='_compute_dossier_stats', store=True,
        help='= Số tiền GN − Σ hồ sơ. Phải = 0 khi submit.')

    @api.depends('dossier_line_ids', 'dossier_line_ids.amount', 'amount')
    def _compute_dossier_stats(self):
        for rec in self:
            rec.dossier_count = len(rec.dossier_line_ids)
            rec.dossier_total = sum(rec.dossier_line_ids.mapped('amount'))
            rec.dossier_balance = rec.amount - rec.dossier_total

    # ------------------------------------------------------------------
    # Onchange: auto-fill 'Số tiền' = Σ giá trị hóa đơn của hồ sơ
    # ------------------------------------------------------------------
    @api.onchange('dossier_line_ids')
    def _onchange_dossier_sum_amount(self):
        """Mỗi khi user thay đổi danh sách hồ sơ (add/edit/remove),
        amount giải ngân tự = Σ giá trị hóa đơn — đảm bảo dossier_balance
        luôn = 0. User vẫn sửa tay được nếu cần override.
        """
        if self.dossier_line_ids:
            self.amount = sum(self.dossier_line_ids.mapped('amount'))

    # ------------------------------------------------------------------
    # Override validation submit — bắt buộc đủ hồ sơ BBN + Hóa đơn
    # ------------------------------------------------------------------
    def _check_ready_to_submit(self):
        super()._check_ready_to_submit()
        for rec in self:
            if not rec.dossier_line_ids:
                raise UserError(_(
                    "Cần ít nhất 1 hồ sơ giải ngân trước khi gửi NH."))
            # BBNT KHÔNG bắt buộc (user feedback) — flexible flow.
            missing_inv = rec.dossier_line_ids.filtered(
                lambda d: not d.invoice_id)
            if missing_inv:
                raise UserError(_(
                    "%(n)s hồ sơ thiếu Hóa đơn. NH yêu cầu mỗi hồ sơ "
                    "phải có hóa đơn từ nhà thầu (đã post sổ kế toán).",
                    n=len(missing_inv)))
            # Σ hồ sơ = số tiền GN
            if abs(rec.dossier_balance) > 1:  # tolerance 1đ VND
                raise UserError(_(
                    "Σ giá trị hồ sơ (%(d)s) khác số tiền giải ngân "
                    "(%(a)s). Chênh lệch: %(b)s. Điều chỉnh cho khớp "
                    "trước khi gửi NH.",
                    d=rec.dossier_total, a=rec.amount,
                    b=rec.dossier_balance))
