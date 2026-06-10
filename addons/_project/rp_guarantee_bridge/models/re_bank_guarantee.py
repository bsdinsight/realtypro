# -*- coding: utf-8 -*-
"""Thêm link rp.contract lên BL NH + đề nghị BL."""
from odoo import api, fields, models


class ReBankGuarantee(models.Model):
    _inherit = 're.bank.guarantee'

    rp_contract_id = fields.Many2one(
        'rp.contract', string='HĐ nhà thầu',
        help='HĐ nhà thầu mà BL này phục vụ (BL thực hiện HĐ / tạm '
             'ứng / bảo hành thường gắn 1-1 với 1 HĐ nhà thầu).')
    rp_project_id = fields.Many2one(
        're.project', string='Dự án',
        related='rp_contract_id.project_id',
        store=True, readonly=True)


class ReGuaranteeRequest(models.Model):
    _inherit = 're.guarantee.request'

    rp_contract_id = fields.Many2one(
        'rp.contract', string='HĐ nhà thầu',
        domain="[('project_id', '=', project_id)]",
        help='HĐ nhà thầu mà BL này phục vụ. Optional. Chỉ hiện HĐ '
             'thuộc Dự án đã chọn — nếu chưa chọn dự án thì hiện tất cả.')

    @api.onchange('project_id')
    def _onchange_project_clear_contract(self):
        """Clear HĐ NT khi đổi dự án để tránh sai lệch dự án ↔ HĐ."""
        if self.rp_contract_id and self.project_id \
                and self.rp_contract_id.project_id != self.project_id:
            self.rp_contract_id = False

    def _prepare_bank_guarantee_vals(self):
        """Copy rp_contract_id sang chứng thư khi phát hành."""
        vals = super()._prepare_bank_guarantee_vals()
        if self.rp_contract_id:
            vals['rp_contract_id'] = self.rp_contract_id.id
        return vals
