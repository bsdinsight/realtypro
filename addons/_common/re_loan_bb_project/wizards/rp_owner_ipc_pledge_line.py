# -*- coding: utf-8 -*-
"""Dòng phân bổ base của IPC vào từng facility (khi bảo đảm cấp HĐTD).

Bản chất: mỗi dòng có số tiền > 0 sẽ sinh MỘT pledge cấp facility
(ring-fence cho facility đó); phần không phân bổ ở lại bể chung HĐTD
(umbrella) như trước. Nhờ vậy user vừa giữ được cách khai "bảo đảm toàn
hợp đồng", vừa chỉ định được facility nào được hưởng bao nhiêu.
"""
from odoo import api, fields, models


class RpOwnerIpcPledgeLine(models.TransientModel):
    _name = 'rp.owner.ipc.pledge.line'
    _description = 'Phân bổ base IPC vào facility'

    wizard_id = fields.Many2one(
        'rp.owner.ipc.pledge.wizard', required=True, ondelete='cascade')
    # KHÔNG để readonly=True ở đây: web client loại bỏ mọi field readonly
    # khi lưu (record.js::_getChanges) → dòng sinh bởi onchange sẽ mất
    # facility_id và create báo "Missing required value". Khoá ở VIEW bằng
    # readonly="1" + force_save="1" thay vì khoá ở Python.
    facility_id = fields.Many2one(
        're.loan.facility', string='Facility (hạn mức)', required=True)
    currency_id = fields.Many2one(
        related='wizard_id.currency_id', readonly=True)

    purpose = fields.Selection(
        related='facility_id.purpose', string='Mục đích', readonly=True)
    amount_limit = fields.Monetary(
        related='facility_id.amount_limit', string='Hạn mức', readonly=True)
    project_alloc = fields.Monetary(
        string='Phân bổ cho dự án', compute='_compute_project_info',
        help='Số tiền hạn mức facility này đã phân bổ cho dự án của IPC.')
    available_before = fields.Monetary(
        string='Khả dụng dự án hiện tại', compute='_compute_project_info',
        help='Trước khi đưa IPC vào.')

    base_amount = fields.Monetary(
        string='Phân bổ base vào facility',
        help='Phần "cộng thêm từ IPC này" dành riêng cho facility này. '
             'Để 0 = không dành riêng, phần đó ở bể chung HĐTD.')
    secured_equiv = fields.Monetary(
        string='≈ Giá trị bảo đảm', compute='_compute_secured_equiv',
        help='Quy ngược từ base theo tỷ lệ cho vay: base ÷ tỷ lệ. Đây là '
             'phần quyền đòi nợ IPC gán riêng cho facility này.')

    @api.depends('facility_id', 'wizard_id.project_id')
    def _compute_project_info(self):
        Alloc = self.env['re.loan.facility.project.allocation']
        for line in self:
            proj = line.wizard_id.project_id
            alloc = Alloc.search([
                ('facility_id', '=', line.facility_id.id),
                ('project_id', '=', proj.id)], limit=1) if proj else Alloc
            line.project_alloc = alloc.amount if alloc else 0.0
            line.available_before = (
                alloc.amount_available_project if alloc else 0.0)

    @api.depends('base_amount', 'wizard_id.advance_rate',
                 'wizard_id.type_id.advance_rate')
    def _compute_secured_equiv(self):
        for line in self:
            w = line.wizard_id
            rate = (w.advance_rate or (w.type_id.advance_rate if w.type_id
                                       else 0.0))
            line.secured_equiv = (
                (line.base_amount or 0.0) / (rate / 100.0) if rate else 0.0)
