# -*- coding: utf-8 -*-
"""
Hồ sơ giải ngân — mỗi giải ngân có thể bao gồm nhiều hồ sơ.

Mỗi hồ sơ gắn với:
  - 1 BBN nghiệm thu (rp.progress.acceptance) — REQUIRED khi submit
  - 1 Hóa đơn (account.move) — REQUIRED khi submit
  - Giá trị giải ngân của hồ sơ

Chuẩn NH VN: NH yêu cầu BBN + hóa đơn để giải ngân (chứng minh khối
lượng đã nghiệm thu + đã có hóa đơn từ nhà thầu).
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class RpLoanDisbursementDossier(models.Model):
    _name = 'rp.loan.disbursement.dossier'
    _description = 'Hồ sơ giải ngân (BBN + Hóa đơn)'
    _order = 'disbursement_id, id'

    disbursement_id = fields.Many2one(
        're.loan.note.disbursement', string='Giải ngân',
        required=True, ondelete='cascade')

    # Related để filter BBNT theo nhà thầu của giải ngân
    disbursement_beneficiary_id = fields.Many2one(
        'res.partner',
        related='disbursement_id.beneficiary_partner_id',
        string='Nhà thầu (từ GN)',
        store=True, readonly=True)

    acceptance_id = fields.Many2one(
        'rp.progress.acceptance',
        string='BBN nghiệm thu',
        domain="[('payment_milestone_id', '!=', False),"
               " ('contract_id.contractor_id', '=', disbursement_beneficiary_id)]",
        help='Pick BBNT của 1 đợt thanh toán HĐ nhà thầu. Dropdown '
             'chỉ hiển thị BBNT của các HĐ có nhà thầu = "Bên nhận '
             'tiền" trên giải ngân. Cần chọn nhà thầu trên GN trước.')
    invoice_id = fields.Many2one(
        'account.move',
        string='Hóa đơn',
        domain="[('move_type','in',['in_invoice','in_refund']),"
               " ('partner_id', '=', disbursement_beneficiary_id),"
               " ('payment_state', 'in',"
               "  ['not_paid', 'partial', 'in_payment'])]",
        help='Hóa đơn từ nhà thầu (vendor bill). Filter theo nhà thầu '
             '(Bên nhận tiền trên giải ngân). Pick được hóa đơn '
             'CHƯA thanh toán + ĐÃ thanh toán MỘT PHẦN (cần giải '
             'ngân thêm). Loại trừ hóa đơn đã trả đủ (paid) hoặc '
             'reversed. Draft/posted đều pick được.')

    # Hiển thị giá trị + số tiền còn lại của hóa đơn (auto-load khi pick)
    invoice_amount_total = fields.Monetary(
        string='Giá trị hóa đơn',
        related='invoice_id.amount_total',
        store=False, readonly=True,
        help='Tổng giá trị hóa đơn vendor bill — auto từ hóa đơn.')
    invoice_amount_remaining = fields.Monetary(
        string='Số tiền còn lại',
        compute='_compute_invoice_remaining',
        store=False, readonly=True,
        help='Số tiền chưa giải ngân của hóa đơn = giá trị hóa đơn − '
             'Σ giá trị hồ sơ giải ngân khác đang link cùng hóa đơn này '
             '(không tính dossier đã cancel). Constraint: số tiền sẽ '
             'thanh toán kỳ này ≤ số tiền còn lại.')

    # Auto từ BBN hoặc Hóa đơn
    contract_id = fields.Many2one(
        'rp.contract', string='HĐ nhà thầu',
        compute='_compute_from_acceptance', store=True)
    contractor_id = fields.Many2one(
        'res.partner', string='Nhà thầu',
        compute='_compute_from_acceptance', store=True)

    amount = fields.Monetary(
        string='Số tiền sẽ thanh toán kỳ này', required=True,
        help='Số tiền sẽ thanh toán cho hóa đơn này trong kỳ giải ngân '
             'hiện tại (KW này). Auto-fill = số tiền còn lại của hóa '
             'đơn khi pick hóa đơn — user vẫn sửa được. Σ các hồ sơ = '
             'tổng số tiền giải ngân của KW.')
    description = fields.Char(string='Diễn giải')

    attachment_ids = fields.Many2many(
        'ir.attachment',
        'rp_loan_dossier_attachment_rel',
        'dossier_id', 'attachment_id',
        string='Tài liệu đính kèm',
        help='Upload file scan BBNT, hóa đơn, chứng từ NH, hợp đồng, '
             'biên bản phụ kèm theo hồ sơ giải ngân.')
    attachment_count = fields.Integer(
        compute='_compute_attachment_count', store=True)

    @api.depends('attachment_ids')
    def _compute_attachment_count(self):
        for rec in self:
            rec.attachment_count = len(rec.attachment_ids)

    currency_id = fields.Many2one(
        related='disbursement_id.currency_id', store=True, readonly=True)
    company_id = fields.Many2one(
        related='disbursement_id.company_id', store=True, readonly=True)
    state = fields.Selection(
        related='disbursement_id.state', store=True, readonly=True)

    @api.depends('acceptance_id', 'invoice_id',
                 'invoice_id.partner_id',
                 'invoice_id.payment_milestone_id.contract_id')
    def _compute_from_acceptance(self):
        for rec in self:
            # Ưu tiên invoice (link rõ ràng qua milestone),
            # fallback acceptance
            contract = False
            contractor = False
            if rec.invoice_id:
                if rec.invoice_id.payment_milestone_id:
                    contract = rec.invoice_id.payment_milestone_id.contract_id
                contractor = rec.invoice_id.partner_id
            if not contract and rec.acceptance_id:
                contract = rec.acceptance_id.contract_id
            if not contractor and rec.acceptance_id:
                contractor = rec.acceptance_id.contractor_id
            rec.contract_id = contract or False
            rec.contractor_id = contractor or False

    @api.depends('invoice_id', 'invoice_id.amount_total', 'amount')
    def _compute_invoice_remaining(self):
        """Số tiền còn lại = giá trị hóa đơn - Σ giá trị các dossier
        khác đang link tới cùng hóa đơn này (không tính dossier đã
        cancel). KHÔNG trừ chính bản thân record này — để user thấy
        đúng còn lại có thể phân bổ.
        """
        for rec in self:
            if not rec.invoice_id:
                rec.invoice_amount_remaining = 0.0
                continue
            origin_id = rec._origin.id if rec._origin else rec.id
            other_dossiers = self.env['rp.loan.disbursement.dossier'].search([
                ('invoice_id', '=', rec.invoice_id.id),
                ('id', '!=', origin_id or 0),
                ('state', '!=', 'cancelled'),
            ])
            other_total = sum(other_dossiers.mapped('amount'))
            rec.invoice_amount_remaining = max(
                0.0, rec.invoice_id.amount_total - other_total)

    @api.onchange('invoice_id')
    def _onchange_invoice_fill_amount(self):
        """Auto-fill amount = số tiền còn lại của hóa đơn khi pick.
        User sửa được, nhưng KHÔNG vượt remaining (constraint).
        """
        if self.invoice_id:
            # Tính lại remaining tại thời điểm onchange
            origin_id = self._origin.id if self._origin else 0
            other_dossiers = self.env['rp.loan.disbursement.dossier'].search([
                ('invoice_id', '=', self.invoice_id.id),
                ('id', '!=', origin_id),
                ('state', '!=', 'cancelled'),
            ])
            other_total = sum(other_dossiers.mapped('amount'))
            remaining = max(
                0.0, self.invoice_id.amount_total - other_total)
            self.amount = remaining
        else:
            self.amount = 0.0

    @api.constrains('amount', 'acceptance_id', 'invoice_id')
    def _check_amount(self):
        for rec in self:
            if rec.amount <= 0:
                raise ValidationError(_(
                    "Số tiền sẽ thanh toán phải > 0."))
            # Validate: amount <= remaining của hóa đơn
            if rec.invoice_id:
                origin_id = rec.id
                other_dossiers = self.env[
                    'rp.loan.disbursement.dossier'].search([
                        ('invoice_id', '=', rec.invoice_id.id),
                        ('id', '!=', origin_id),
                        ('state', '!=', 'cancelled'),
                    ])
                other_total = sum(other_dossiers.mapped('amount'))
                remaining = rec.invoice_id.amount_total - other_total
                if rec.amount > remaining + 0.01:
                    raise ValidationError(_(
                        "Số tiền sẽ thanh toán kỳ này (%(amount)s) "
                        "vượt quá số tiền còn lại của hóa đơn "
                        "(%(remaining)s). Hóa đơn %(invoice)s đã được "
                        "phân bổ ở các hồ sơ giải ngân khác.") % {
                            'amount': '{:,.0f}'.format(rec.amount),
                            'remaining': '{:,.0f}'.format(remaining),
                            'invoice': rec.invoice_id.name or '/',
                        })
