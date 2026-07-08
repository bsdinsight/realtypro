# -*- coding: utf-8 -*-
"""Phụ lục bảo lãnh — gia hạn / điều chỉnh giá trị.

VN gia hạn bảo lãnh rất thường xuyên (gia hạn HĐ → gia hạn BL). Mỗi phụ
lục ghi nhận thay đổi theo LOẠI điều chỉnh, xác nhận sẽ áp vào chứng thư
gốc + log chatter:

* Gia hạn thời gian → đặt ngày hết hạn mới (phải muộn hơn hiện tại)
* Tăng giá trị      → CỘNG số tiền vào giá trị bảo lãnh
* Giảm giá trị      → TRỪ số tiền khỏi giá trị bảo lãnh (không âm)
* Khác             → chỉ ghi diễn giải
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
    new_date_expiry = fields.Date(
        string='Ngày hết hạn mới',
        help='Chỉ dùng cho loại "Gia hạn thời gian" — phải muộn hơn '
             'ngày hết hạn hiện tại.')
    amount_change = fields.Monetary(
        string='Số tiền tăng / giảm',
        help='Số tiền CỘNG (Tăng giá trị) hoặc TRỪ (Giảm giá trị) vào '
             'giá trị bảo lãnh. Nhập số dương.')
    currency_id = fields.Many2one(
        related='guarantee_id.currency_id')
    note = fields.Char(string='Diễn giải')
    applied = fields.Boolean(string='Đã áp dụng', readonly=True)

    # snapshot để hiển thị/đối chiếu
    value_before = fields.Char(string='Trước', readonly=True)
    value_after = fields.Char(string='Sau', readonly=True)

    @api.onchange('amendment_type')
    def _onchange_amendment_type(self):
        """Xóa field không liên quan khi đổi loại — tránh nhầm."""
        if self.amendment_type != 'extend':
            self.new_date_expiry = False
        if self.amendment_type not in ('increase', 'decrease'):
            self.amount_change = 0.0

    def action_apply(self):
        for rec in self:
            if rec.applied:
                raise UserError(_("Phụ lục này đã áp dụng."))
            g = rec.guarantee_id
            cur = g.currency_id

            if rec.amendment_type == 'extend':
                if not rec.new_date_expiry:
                    raise UserError(_(
                        "Gia hạn thời gian: nhập 'Ngày hết hạn mới'."))
                if g.date_expiry and rec.new_date_expiry <= g.date_expiry:
                    raise UserError(_(
                        "Ngày hết hạn mới (%(n)s) phải muộn hơn ngày hết "
                        "hạn hiện tại (%(o)s).",
                        n=rec.new_date_expiry, o=g.date_expiry))
                before, after = str(g.date_expiry or ''), str(rec.new_date_expiry)
                g.date_expiry = rec.new_date_expiry
                desc = _("Gia hạn: %(o)s → %(n)s", o=before, n=after)

            elif rec.amendment_type in ('increase', 'decrease'):
                if not rec.amount_change or rec.amount_change <= 0:
                    raise UserError(_(
                        "Nhập 'Số tiền tăng / giảm' (số dương)."))
                old_amt = g.amount
                if rec.amendment_type == 'increase':
                    new_amt = old_amt + rec.amount_change
                else:
                    new_amt = old_amt - rec.amount_change
                    if cur.compare_amounts(new_amt, 0.0) < 0:
                        raise UserError(_(
                            "Giảm %(d)s vượt giá trị bảo lãnh hiện tại "
                            "(%(o)s) — giá trị sau khi giảm sẽ âm.",
                            d='{:,.0f}'.format(rec.amount_change),
                            o='{:,.0f}'.format(old_amt)))
                before = '{:,.0f}'.format(old_amt)
                after = '{:,.0f}'.format(new_amt)
                g.amount = new_amt
                sign = '+' if rec.amendment_type == 'increase' else '−'
                desc = _("Giá trị: %(o)s %(s)s %(d)s = %(n)s",
                         o=before, s=sign,
                         d='{:,.0f}'.format(rec.amount_change), n=after)
            else:  # other
                before = after = ''
                desc = rec.note or _("Điều chỉnh khác")

            rec.applied = True
            rec.value_before = before
            rec.value_after = after
            g.message_post(body=_(
                "<b>Phụ lục bảo lãnh %(n)s</b> (%(t)s): %(d)s",
                n=rec.name or '',
                t=dict(rec._fields['amendment_type'].selection).get(
                    rec.amendment_type),
                d=desc))
        return True
