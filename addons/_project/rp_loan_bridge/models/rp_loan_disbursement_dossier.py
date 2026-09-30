# -*- coding: utf-8 -*-
"""Hồ sơ giải ngân — phần nối với bộ Thi công của Realty.

Lõi (hoá đơn, số tiền, phân bổ theo hoá đơn) nằm ở `re_loan_dossier` để
khách chỉ mua phân hệ vay vẫn dùng được. Ở đây thêm đúng hai thứ cần
model của bộ Thi công: biên bản nghiệm thu và hợp đồng nhà thầu.
"""
from odoo import api, fields, models


class RpLoanDisbursementDossier(models.Model):
    _inherit = 'rp.loan.disbursement.dossier'

    acceptance_id = fields.Many2one(
        'rp.progress.acceptance',
        string='BBN nghiệm thu',
        domain="[('payment_milestone_id', '!=', False),"
               " ('contract_id.contractor_id', '=', disbursement_beneficiary_id)]",
        help='BBNT của một đợt thanh toán HĐ nhà thầu. Danh sách chỉ '
             'hiện BBNT của HĐ có nhà thầu = "Bên nhận tiền" trên giải '
             'ngân — chọn bên nhận tiền trước.')
    contract_id = fields.Many2one(
        'rp.contract', string='HĐ nhà thầu',
        compute='_compute_dossier_source', store=True)

    @api.depends('invoice_id', 'invoice_id.partner_id',
                 'invoice_id.payment_milestone_id.contract_id',
                 'acceptance_id')
    def _compute_dossier_source(self):
        """Ưu tiên hoá đơn (liên kết rõ qua đợt thanh toán), thiếu thì
        lấy từ biên bản nghiệm thu."""
        for rec in self:
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
