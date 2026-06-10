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
               " ('partner_id', '=', disbursement_beneficiary_id)]",
        help='Hóa đơn từ nhà thầu (vendor bill). Filter theo nhà thầu '
             '(Bên nhận tiền trên giải ngân). Tất cả state hiển thị '
             '— draft/posted đều pick được.')

    # Auto từ BBN hoặc Hóa đơn
    contract_id = fields.Many2one(
        'rp.contract', string='HĐ nhà thầu',
        compute='_compute_from_acceptance', store=True)
    contractor_id = fields.Many2one(
        'res.partner', string='Nhà thầu',
        compute='_compute_from_acceptance', store=True)

    amount = fields.Monetary(
        string='Giá trị hóa đơn', required=True,
        help='Giá trị giải ngân của hồ sơ này. Auto-fill = '
             'invoice.amount_total khi pick hóa đơn (user vẫn sửa được). '
             'Σ các hồ sơ = tổng số tiền giải ngân.')
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

    @api.onchange('invoice_id')
    def _onchange_invoice_fill_amount(self):
        """Auto-fill amount = invoice.amount_total mỗi khi pick hóa đơn.
        User vẫn sửa tay được sau đó nếu cần override.
        """
        if self.invoice_id:
            self.amount = self.invoice_id.amount_total
        else:
            self.amount = 0.0

    @api.constrains('amount', 'acceptance_id', 'invoice_id')
    def _check_amount(self):
        for rec in self:
            if rec.amount <= 0:
                raise ValidationError(_(
                    "Giá trị hồ sơ giải ngân phải > 0."))
