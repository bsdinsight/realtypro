# -*- coding: utf-8 -*-
"""Hồ sơ giải ngân — một lần giải ngân gồm nhiều hồ sơ, mỗi hồ sơ một
hoá đơn của nhà thầu.

Ngân hàng không giải ngân theo một con số tổng: phải chỉ ra tiền đi đâu.
Phần lõi ở đây chỉ cần HOÁ ĐƠN — thứ mọi khách đều có trong kế toán.
Biên bản nghiệm thu và hợp đồng nhà thầu là chỗ nối MỞ: khách dùng bộ
Thi công của Realty thì `rp_loan_bridge` gắn vào; khách có hệ nghiệm
thu / hợp đồng riêng thì kế thừa model này mà gắn.

Giữ tên model cũ `rp.loan.disbursement.dossier` khi tách ra khỏi
`rp_loan_bridge`: đổi tên là phải chuyển dữ liệu của khách đang chạy,
đổi lấy một cái tên đẹp hơn.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class RpLoanDisbursementDossier(models.Model):
    _name = 'rp.loan.disbursement.dossier'
    _description = 'Hồ sơ giải ngân (hoá đơn)'
    _order = 'disbursement_id, id'

    disbursement_id = fields.Many2one(
        're.loan.note.disbursement', string='Giải ngân',
        required=True, ondelete='cascade')

    # Related để lọc hoá đơn theo bên nhận tiền của giải ngân
    disbursement_beneficiary_id = fields.Many2one(
        'res.partner',
        related='disbursement_id.beneficiary_partner_id',
        string='Nhà thầu (từ GN)',
        store=True, readonly=True)

    invoice_id = fields.Many2one(
        'account.move',
        string='Hóa đơn',
        domain="[('move_type','in',['in_invoice','in_refund']),"
               " ('partner_id', '=', disbursement_beneficiary_id),"
               " ('payment_state', 'in',"
               "  ['not_paid', 'partial', 'in_payment'])]",
        help='Hóa đơn từ nhà thầu (vendor bill). Lọc theo bên nhận tiền '
             'trên giải ngân. Chọn được hoá đơn CHƯA thanh toán và ĐÃ '
             'thanh toán MỘT PHẦN; bỏ hoá đơn đã trả đủ hoặc đã đảo.')

    invoice_amount_total = fields.Monetary(
        string='Giá trị hóa đơn',
        related='invoice_id.amount_total',
        store=False, readonly=True)
    invoice_amount_remaining = fields.Monetary(
        string='Số tiền còn lại',
        compute='_compute_invoice_remaining',
        store=False, readonly=True,
        help='Giá trị hoá đơn − Σ các hồ sơ giải ngân khác đang gắn '
             'cùng hoá đơn này (bỏ hồ sơ đã huỷ).')

    contractor_id = fields.Many2one(
        'res.partner', string='Nhà thầu',
        compute='_compute_dossier_source', store=True)

    amount = fields.Monetary(
        string='Số tiền sẽ thanh toán kỳ này', required=True,
        help='Số tiền thanh toán cho hoá đơn này trong lần giải ngân '
             'hiện tại. Tự điền bằng số còn lại của hoá đơn khi chọn '
             'hoá đơn — sửa được. Σ các hồ sơ = số tiền giải ngân.')
    description = fields.Char(string='Diễn giải')

    attachment_ids = fields.Many2many(
        'ir.attachment',
        'rp_loan_dossier_attachment_rel',
        'dossier_id', 'attachment_id',
        string='Tài liệu đính kèm',
        help='Bản scan hoá đơn, biên bản nghiệm thu, chứng từ NH.')
    attachment_count = fields.Integer(
        compute='_compute_attachment_count', store=True)

    currency_id = fields.Many2one(
        related='disbursement_id.currency_id', store=True, readonly=True)
    company_id = fields.Many2one(
        related='disbursement_id.company_id', store=True, readonly=True)
    state = fields.Selection(
        related='disbursement_id.state', store=True, readonly=True)

    @api.depends('attachment_ids')
    def _compute_attachment_count(self):
        for rec in self:
            rec.attachment_count = len(rec.attachment_ids)

    @api.depends('invoice_id', 'invoice_id.partner_id')
    def _compute_dossier_source(self):
        """Nhà thầu suy từ hoá đơn.

        Module cầu nối với bộ Thi công (hoặc module riêng của khách)
        ghi đè hàm này để lấy thêm từ biên bản nghiệm thu / hợp đồng.
        """
        for rec in self:
            rec.contractor_id = rec.invoice_id.partner_id or False

    def _other_dossiers_amount(self, invoice, exclude_id):
        """Σ số tiền các hồ sơ KHÁC đang gắn cùng hoá đơn."""
        if not invoice:
            return 0.0
        others = self.search([
            ('invoice_id', '=', invoice.id),
            ('id', '!=', exclude_id or 0),
            ('state', '!=', 'cancelled'),
        ])
        return sum(others.mapped('amount'))

    @api.depends('invoice_id', 'invoice_id.amount_total', 'amount')
    def _compute_invoice_remaining(self):
        # KHÔNG trừ chính bản ghi này — để người dùng thấy đúng phần
        # còn phân bổ được.
        for rec in self:
            if not rec.invoice_id:
                rec.invoice_amount_remaining = 0.0
                continue
            origin_id = rec._origin.id if rec._origin else rec.id
            other_total = rec._other_dossiers_amount(
                rec.invoice_id, origin_id)
            rec.invoice_amount_remaining = max(
                0.0, rec.invoice_id.amount_total - other_total)

    @api.onchange('invoice_id')
    def _onchange_invoice_fill_amount(self):
        """Chọn hoá đơn thì điền sẵn số còn lại; sửa được."""
        if self.invoice_id:
            origin_id = self._origin.id if self._origin else 0
            other_total = self._other_dossiers_amount(
                self.invoice_id, origin_id)
            self.amount = max(
                0.0, self.invoice_id.amount_total - other_total)
        else:
            self.amount = 0.0

    @api.constrains('amount', 'invoice_id')
    def _check_amount(self):
        for rec in self:
            if rec.amount <= 0:
                raise ValidationError(_(
                    'Số tiền sẽ thanh toán phải > 0.'))
            if rec.invoice_id:
                other_total = rec._other_dossiers_amount(
                    rec.invoice_id, rec.id)
                remaining = rec.invoice_id.amount_total - other_total
                if rec.amount > remaining + 0.01:
                    raise ValidationError(_(
                        'Số tiền sẽ thanh toán kỳ này (%(amount)s) vượt '
                        'số tiền còn lại của hoá đơn (%(remaining)s). '
                        'Hoá đơn %(invoice)s đã được phân bổ ở hồ sơ '
                        'giải ngân khác.',
                        amount='{:,.0f}'.format(rec.amount),
                        remaining='{:,.0f}'.format(remaining),
                        invoice=rec.invoice_id.name or '/'))
