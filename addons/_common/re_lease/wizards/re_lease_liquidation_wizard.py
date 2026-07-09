# -*- coding: utf-8 -*-
"""Wizard thanh lý HĐ thuê — kiểm kê tình trạng, quyết toán, hoàn/khấu
trừ ký cược, xác nhận trả tài sản. Sinh biên bản thanh lý.

Thực tế biên bản thanh lý gồm: tình trạng tài sản, quyết toán mọi khoản
(tiền thuê còn lại, sửa chữa, phạt), hoàn hoặc khấu trừ tiền cọc.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ReLeaseLiquidationWizard(models.TransientModel):
    _name = 're.lease.liquidation.wizard'
    _description = 'Wizard thanh lý HĐ thuê'

    contract_id = fields.Many2one(
        're.lease.contract', string='HĐ thuê', required=True,
        ondelete='cascade')
    currency_id = fields.Many2one(related='contract_id.currency_id')
    liquidation_date = fields.Date(
        string='Ngày thanh lý', required=True,
        default=fields.Date.context_today)
    deposit = fields.Monetary(
        related='contract_id.deposit', string='Ký cược đã nhận/đặt',
        readonly=True)
    penalty_amount = fields.Monetary(
        related='contract_id.penalty_amount', string='Phạt/bồi thường',
        readonly=True)
    repair_deduction = fields.Monetary(
        string='Khấu trừ sửa chữa / hư hỏng')
    other_deduction = fields.Monetary(string='Khấu trừ khác')
    deposit_refund = fields.Monetary(
        string='Hoàn ký cược', compute='_compute_amounts', store=True,
        readonly=False,
        help='= Ký cược − khấu trừ (không âm). Có thể sửa tay.')
    final_settlement = fields.Monetary(
        string='Quyết toán cuối (thu/trả)', compute='_compute_amounts',
        store=True, readonly=False,
        help='Số dương = phải trả lại bên kia; âm = còn phải thu.')
    asset_return_ok = fields.Boolean(string='Đã nhận/trả lại tài sản')
    note = fields.Text(string='Ghi chú / tình trạng tài sản')

    @api.depends('deposit', 'repair_deduction', 'other_deduction',
                 'penalty_amount')
    def _compute_amounts(self):
        for w in self:
            deduct = (w.repair_deduction or 0.0) + (w.other_deduction or 0.0)
            refund = (w.deposit or 0.0) - deduct
            w.deposit_refund = refund if refund > 0 else 0.0
            # Quyết toán cuối gợi ý: hoàn cọc − phạt (bên đi thuê nhận
            # lại). Người dùng sửa theo thực tế đối chiếu.
            w.final_settlement = w.deposit_refund - (w.penalty_amount or 0.0)

    def action_confirm(self):
        self.ensure_one()
        c = self.contract_id
        if c.liquidated:
            raise UserError(_('HĐ đã thanh lý.'))
        c._apply_liquidation({
            'liquidation_date': self.liquidation_date,
            'repair_deduction': self.repair_deduction,
            'other_deduction': self.other_deduction,
            'deposit_refund': self.deposit_refund,
            'final_settlement': self.final_settlement,
            'asset_return_ok': self.asset_return_ok,
        })
        if self.note:
            c.message_post(body=_('Tình trạng tài sản khi thanh lý: %s',
                                  self.note))
        return {'type': 'ir.actions.act_window_close'}
