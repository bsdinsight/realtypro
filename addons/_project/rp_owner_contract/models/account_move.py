# -*- coding: utf-8 -*-
"""account.move — hoá đơn ĐẦU RA phát hành cho Chủ đầu tư (doanh thu).

Đối xứng với hoá đơn nhà thầu (in_invoice, phía chi phí) do rp_progress
gắn link. Ở đây gắn out_invoice với HĐ / đợt thanh toán của CĐT để tổng
hợp doanh thu và khoản phải thu theo dự án.
"""
from odoo import fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    owner_contract_id = fields.Many2one(
        'rp.owner.contract', string='HĐ với CĐT', index=True, copy=False)
    owner_milestone_id = fields.Many2one(
        'rp.owner.payment.milestone', string='Đợt thanh toán CĐT',
        index=True, copy=False)
    owner_project_id = fields.Many2one(
        related='owner_contract_id.project_id', store=True, readonly=True,
        string='Dự án (đầu ra)')
