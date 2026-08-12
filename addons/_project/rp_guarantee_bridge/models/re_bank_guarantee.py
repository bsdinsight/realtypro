# -*- coding: utf-8 -*-
"""Thêm link hợp đồng lên BL NH + đề nghị BL.

Hai chiều, đúng hai vai của tổng thầu:
- `rp_contract_id`  — BL mà NHÀ THẦU PHỤ nộp cho mình (BL thực hiện HĐ,
  tạm ứng, bảo hành của hợp đồng thầu phụ).
- `owner_contract_id` — BL mà MÌNH phát hành cho CHỦ ĐẦU TƯ theo hợp đồng
  tổng thầu. Đây là ca "vay để đảm bảo thực hiện hợp đồng" (anh Đại nêu
  2026-08-10): hạn mức bảo lãnh gắn HĐ với CĐT, chứng thư phát hành cũng
  phải trỏ về đúng hợp đồng đó thì chuỗi HĐ CĐT → IPC → TSBĐ → hạn mức →
  chứng thư mới khép kín.
"""
from odoo import api, fields, models


class ReBankGuarantee(models.Model):
    _inherit = 're.bank.guarantee'

    rp_contract_id = fields.Many2one(
        'rp.contract', string='HĐ nhà thầu',
        help='HĐ nhà thầu mà BL này phục vụ (BL thực hiện HĐ / tạm '
             'ứng / bảo hành thường gắn 1-1 với 1 HĐ nhà thầu).')
    owner_contract_id = fields.Many2one(
        'rp.owner.contract', string='HĐ với CĐT',
        help='HĐ ký với chủ đầu tư mà BL này bảo đảm (BL thực hiện HĐ / '
             'tạm ứng mình phát hành cho CĐT).')
    rp_project_id = fields.Many2one(
        're.project', string='Dự án',
        compute='_compute_rp_project_id', store=True, readonly=True)

    @api.depends('rp_contract_id.project_id', 'owner_contract_id.project_id')
    def _compute_rp_project_id(self):
        for rec in self:
            rec.rp_project_id = (rec.rp_contract_id.project_id
                                 or rec.owner_contract_id.project_id)


class ReGuaranteeRequest(models.Model):
    _inherit = 're.guarantee.request'

    rp_contract_id = fields.Many2one(
        'rp.contract', string='HĐ nhà thầu',
        domain="[('project_id', '=', project_id)]",
        help='HĐ nhà thầu mà BL này phục vụ. Optional. Chỉ hiện HĐ '
             'thuộc Dự án đã chọn — nếu chưa chọn dự án thì hiện tất cả.')

    owner_contract_id = fields.Many2one(
        'rp.owner.contract', string='HĐ với CĐT',
        domain="[('project_id', '=', project_id)]",
        help='HĐ với chủ đầu tư mà BL này bảo đảm. Tự điền theo hạn mức '
             'bảo lãnh nếu hạn mức đã khai HĐ với CĐT.')

    @api.onchange('facility_id')
    def _onchange_facility_fill_owner_contract(self):
        """Hạn mức đã gắn HĐ với CĐT → điền sẵn cho đề nghị BL."""
        fac = self.facility_id
        if fac and getattr(fac, 'owner_contract_id', False):
            self.owner_contract_id = fac.owner_contract_id
            if not self.project_id:
                self.project_id = fac.owner_contract_id.project_id

    @api.onchange('project_id')
    def _onchange_project_clear_contract(self):
        """Clear HĐ NT khi đổi dự án để tránh sai lệch dự án ↔ HĐ."""
        if self.rp_contract_id and self.project_id \
                and self.rp_contract_id.project_id != self.project_id:
            self.rp_contract_id = False
        if self.owner_contract_id and self.project_id \
                and self.owner_contract_id.project_id != self.project_id:
            self.owner_contract_id = False

    def _prepare_bank_guarantee_vals(self):
        """Copy rp_contract_id sang chứng thư khi phát hành."""
        vals = super()._prepare_bank_guarantee_vals()
        if self.rp_contract_id:
            vals['rp_contract_id'] = self.rp_contract_id.id
        if self.owner_contract_id:
            vals['owner_contract_id'] = self.owner_contract_id.id
        return vals
