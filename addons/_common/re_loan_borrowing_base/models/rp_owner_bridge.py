# -*- coding: utf-8 -*-
"""Bridge: biến động sản lượng/thanh toán CĐT → định giá lại TSBĐ
quyền đòi nợ (tự động, có audit trail)."""
from odoo import _, api, models


class RpOwnerAcceptance(models.Model):
    _inherit = 'rp.owner.acceptance'

    def action_approve(self):
        res = super().action_approve()
        self.mapped('contract_id')._sync_receivable_collaterals(
            reason=_('BBNT được CĐT duyệt'))
        return res


class RpOwnerPayment(models.Model):
    _inherit = 'rp.owner.payment'

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        recs.mapped('contract_id')._sync_receivable_collaterals(
            reason=_('CĐT thanh toán'))
        return recs

    def write(self, vals):
        res = super().write(vals)
        if 'amount' in vals or 'contract_id' in vals:
            self.mapped('contract_id')._sync_receivable_collaterals(
                reason=_('Sửa thanh toán CĐT'))
        return res

    def unlink(self):
        contracts = self.mapped('contract_id')
        res = super().unlink()
        contracts._sync_receivable_collaterals(
            reason=_('Xoá thanh toán CĐT'))
        return res


class RpOwnerContract(models.Model):
    _inherit = 'rp.owner.contract'

    def _sync_receivable_collaterals(self, reason=''):
        collaterals = self.env['re.loan.collateral'].search(
            [('owner_contract_id', 'in', self.ids)])
        collaterals._sync_receivable_valuation(reason=reason)
