# -*- coding: utf-8 -*-
"""Hồ sơ giải ngân: khi chọn tạm ứng → chọn bảo lãnh nhận từ nhà thầu.

Bảo lãnh tạm ứng (hoàn tạm ứng) là chứng thư nhà thầu phụ nộp bảo đảm
sẽ hoàn tạm ứng nếu không thực hiện. Khi giải ngân tạm ứng, gắn bảo
lãnh này để truy vết + kiểm tra bao phủ.
"""
from odoo import _, api, fields, models


class RpLoanDisbursementDossier(models.Model):
    _inherit = 'rp.loan.disbursement.dossier'

    # nhà thầu của tạm ứng — dùng để lọc bảo lãnh
    advance_partner_id = fields.Many2one(
        'res.partner', string='Nhà thầu (tạm ứng)',
        related='advance_payment_id.partner_id', store=True)

    guarantee_id = fields.Many2one(
        'rp.contract.guarantee', string='Bảo lãnh nhận từ nhà thầu',
        domain="[('contractor_id', '=', advance_partner_id),"
               " ('state', '=', 'active')]",
        help='Chọn bảo lãnh nhà thầu phụ đã nộp (thường là bảo lãnh '
             'tạm ứng / hoàn tạm ứng). Dropdown lọc theo đúng nhà thầu '
             'của tạm ứng, chỉ hiện chứng thư đang hiệu lực.')
    guarantee_amount = fields.Monetary(
        related='guarantee_id.amount', string='Giá trị bảo lãnh',
        readonly=True)
    guarantee_date_expiry = fields.Date(
        related='guarantee_id.date_expiry', string='BL hết hạn',
        readonly=True)
    guarantee_type = fields.Selection(
        related='guarantee_id.guarantee_type', string='Loại BL')
    guarantee_shortfall = fields.Boolean(
        string='Bảo lãnh không đủ bao phủ',
        compute='_compute_guarantee_shortfall',
        help='Giá trị bảo lãnh nhỏ hơn số tiền tạm ứng giải ngân.')

    @api.depends('guarantee_id', 'guarantee_id.amount', 'amount')
    def _compute_guarantee_shortfall(self):
        for rec in self:
            rec.guarantee_shortfall = bool(
                rec.guarantee_id
                and rec.guarantee_id.amount < rec.amount)

    @api.onchange('advance_payment_id')
    def _onchange_advance_clear_guarantee(self):
        """Đổi tạm ứng → bỏ bảo lãnh nếu không còn đúng nhà thầu."""
        if (self.guarantee_id
                and self.guarantee_id.contractor_id
                != self.advance_partner_id):
            self.guarantee_id = False

    @api.onchange('guarantee_id', 'amount')
    def _onchange_guarantee_warn(self):
        if self.guarantee_id and self.guarantee_id.amount < self.amount:
            return {'warning': {
                'title': _("Bảo lãnh không đủ bao phủ"),
                'message': _(
                    "Giá trị bảo lãnh (%(g)s) nhỏ hơn số tiền tạm ứng "
                    "giải ngân kỳ này (%(a)s). Kiểm tra lại hoặc yêu cầu "
                    "nhà thầu bổ sung bảo lãnh.",
                    g='{:,.0f}'.format(self.guarantee_id.amount),
                    a='{:,.0f}'.format(self.amount)),
            }}
