# -*- coding: utf-8 -*-
"""Phụ lục bảo lãnh — gia hạn / điều chỉnh giá trị.

VN gia hạn bảo lãnh rất thường xuyên (gia hạn HĐ → gia hạn BL). Mỗi phụ
lục ghi nhận thay đổi, xác nhận sẽ áp vào chứng thư gốc + log chatter.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class RpContractGuaranteeAmendment(models.Model):
    _name = 'rp.contract.guarantee.amendment'
    _description = 'Phụ lục bảo lãnh HĐ nhà thầu'
    _order = 'date_effective, id'

    guarantee_id = fields.Many2one(
        'rp.contract.guarantee', string='Bảo lãnh', required=True,
        ondelete='cascade')
    name = fields.Char(string='Số phụ lục')
    amendment_type = fields.Selection(
        [('extend',   'Gia hạn thời gian'),
         ('increase', 'Tăng giá trị'),
         ('decrease', 'Giảm giá trị'),
         ('other',    'Khác')],
        string='Loại điều chỉnh', required=True, default='extend')
    date_effective = fields.Date(
        string='Ngày hiệu lực', required=True,
        default=fields.Date.context_today)
    new_date_expiry = fields.Date(string='Ngày hết hạn mới')
    new_amount = fields.Monetary(string='Giá trị bảo lãnh mới')
    currency_id = fields.Many2one(
        related='guarantee_id.currency_id')
    note = fields.Char(string='Diễn giải')
    applied = fields.Boolean(string='Đã áp dụng', readonly=True)

    old_value = fields.Char(string='Trước', readonly=True)
    new_value = fields.Char(string='Sau', readonly=True)

    def action_apply(self):
        for rec in self:
            if rec.applied:
                raise UserError(_("Phụ lục này đã áp dụng."))
            g = rec.guarantee_id
            changes = []
            if rec.new_date_expiry:
                changes.append(_("hết hạn %(o)s → %(n)s",
                                 o=g.date_expiry, n=rec.new_date_expiry))
                g.date_expiry = rec.new_date_expiry
            if rec.new_amount:
                changes.append(_("giá trị %(o)s → %(n)s",
                                 o='{:,.0f}'.format(g.amount),
                                 n='{:,.0f}'.format(rec.new_amount)))
                g.amount = rec.new_amount
            rec.applied = True
            rec.old_value = g.date_expiry and str(g.date_expiry) or ''
            if changes:
                g.message_post(body=_(
                    "<b>Phụ lục bảo lãnh %(n)s:</b> %(c)s",
                    n=rec.name or '', c='; '.join(changes)))
        return True

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records.action_apply()
        return records
