# -*- coding: utf-8 -*-
"""KW: cảnh báo (không chặn) khi rút vượt khả dụng thực tế."""
from odoo import api, fields, models


class ReLoanNote(models.Model):
    _inherit = 're.loan.note'

    exceeds_available = fields.Boolean(
        string='Vượt khả dụng thực tế',
        compute='_compute_exceeds_available',
        help='Số tiền KW vượt Khả dụng thực tế của facility (theo '
             'borrowing base). CHỈ CẢNH BÁO — NH là bên quyết định '
             'cuối; muốn tăng khả dụng cần nghiệm thu thêm sản lượng '
             'với CĐT hoặc bổ sung TSBĐ.')

    @api.depends('amount', 'facility_id', 'state')
    def _compute_exceeds_available(self):
        for rec in self:
            rec.exceeds_available = bool(
                rec.facility_id
                and rec.state in ('draft', 'sent_to_bank')
                and (rec.facility_id.has_own_pledges
                     or rec.facility_id.credit_contract_id
                     .has_any_pledges)
                and rec.amount
                > rec.facility_id.amount_available_effective + 0.01)
