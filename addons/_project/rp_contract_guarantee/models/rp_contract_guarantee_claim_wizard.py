# -*- coding: utf-8 -*-
"""Wizard yêu cầu thanh toán bảo lãnh (claim) khi nhà thầu vi phạm."""
from odoo import _, fields, models
from odoo.exceptions import UserError


class RpContractGuaranteeClaimWizard(models.TransientModel):
    _name = 'rp.contract.guarantee.claim.wizard'
    _description = 'Yêu cầu thanh toán bảo lãnh'

    guarantee_id = fields.Many2one(
        'rp.contract.guarantee', required=True, readonly=True,
        ondelete='cascade')
    currency_id = fields.Many2one(related='guarantee_id.currency_id')
    claim_date = fields.Date(
        string='Ngày yêu cầu', required=True,
        default=fields.Date.context_today)
    claim_amount = fields.Monetary(string='Số tiền yêu cầu', required=True)
    claim_reason = fields.Text(
        string='Lý do', required=True,
        help='Căn cứ yêu cầu thực hiện nghĩa vụ bảo lãnh: nhà thầu từ '
             'chối thực hiện / vi phạm hợp đồng / chậm tiến độ do lỗi '
             'nhà thầu…')

    def action_confirm(self):
        self.ensure_one()
        g = self.guarantee_id
        if self.claim_amount <= 0:
            raise UserError(_("Số tiền yêu cầu phải > 0."))
        if self.claim_amount > g.amount:
            raise UserError(_(
                "Số tiền yêu cầu (%(a)s) vượt giá trị bảo lãnh (%(g)s).",
                a='{:,.0f}'.format(self.claim_amount),
                g='{:,.0f}'.format(g.amount)))
        g.write({
            'state': 'claimed',
            'claim_date': self.claim_date,
            'claim_amount': self.claim_amount,
            'claim_reason': self.claim_reason,
        })
        g.message_post(body=_(
            "<b>Yêu cầu thanh toán bảo lãnh:</b> %(a)s ngày %(d)s.<br/>"
            "Lý do: %(r)s",
            a='{:,.0f}'.format(self.claim_amount),
            d=self.claim_date, r=self.claim_reason))
        return {'type': 'ir.actions.act_window_close'}
