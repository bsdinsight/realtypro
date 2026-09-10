# -*- coding: utf-8 -*-
"""Phụ lục chứng thư BL — gia hạn, đổi giá trị, đổi beneficiary, huỷ."""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


AMENDMENT_TYPES = [
    ('extension', 'Gia hạn'),
    ('amount',    'Đổi giá trị BL'),
    ('beneficiary', 'Đổi beneficiary'),
    ('cancel',    'Huỷ trước hạn'),
    ('other',     'Khác'),
]


class ReBankGuaranteeAmendment(models.Model):
    _name = 're.bank.guarantee.amendment'
    _description = 'Phụ lục chứng thư BL'
    _inherit = ['mail.thread']
    _order = 'date_effective desc, id desc'

    name = fields.Char(
        string='Số phụ lục', required=True, copy=False, tracking=True,
        help='Số phụ lục NH cấp.')
    guarantee_id = fields.Many2one(
        're.bank.guarantee', string='Chứng thư BL',
        required=True, ondelete='cascade', tracking=True)
    amendment_type = fields.Selection(
        AMENDMENT_TYPES, string='Loại phụ lục', required=True,
        tracking=True)
    date_effective = fields.Date(
        string='Ngày hiệu lực', required=True,
        default=fields.Date.context_today)

    # Giá trị mới — hiển thị có điều kiện
    new_date_expiry = fields.Date(string='Ngày hết hạn mới')
    new_amount = fields.Monetary(string='Giá trị BL mới')
    new_beneficiary_partner_id = fields.Many2one(
        'res.partner', string='Beneficiary mới')

    description = fields.Text(string='Diễn giải')
    value_old = fields.Char(string='Giá trị cũ', readonly=True)
    value_new = fields.Char(string='Giá trị mới', readonly=True)

    state = fields.Selection(
        [('draft',   'Nháp'),
         ('applied', 'Đã áp dụng')],
        string='Trạng thái', default='draft', required=True, tracking=True)

    currency_id = fields.Many2one(
        related='guarantee_id.currency_id', store=True, readonly=True)
    company_id = fields.Many2one(
        related='guarantee_id.company_id', store=True, readonly=True)

    @api.constrains('amendment_type', 'new_amount', 'new_date_expiry')
    def _check_new_values(self):
        for am in self:
            if am.amendment_type == 'amount' and am.new_amount <= 0:
                raise ValidationError(_("Giá trị BL mới phải > 0."))
            if (am.amendment_type == 'extension'
                    and not am.new_date_expiry):
                raise ValidationError(_(
                    "Phụ lục gia hạn cần Ngày hết hạn mới."))

    @staticmethod
    def _fmt_date(d):
        """Ngày trong ô "Giá trị cũ / mới" viết theo lối Việt Nam.

        Hai ô này là Char nên ngày phải tự định dạng. Để nguyên
        `str(date)` ra 2026-11-30 — đúng với máy nhưng người đọc hồ sơ
        gia hạn phải dịch lại trong đầu, và dễ đọc nhầm ngày với tháng
        khi đối chiếu với văn bản ngân hàng.
        """
        return d.strftime('%d-%m-%Y') if d else ''

    def unlink(self):
        """Phụ lục ĐÃ ÁP DỤNG thì không xoá được.

        Áp dụng phụ lục đã ghi thẳng giá trị mới lên chứng thư — gia
        hạn đổi ngày hết hạn, đổi giá trị đổi số tiền chiếm hạn mức.
        Xoá dòng phụ lục đi thì chứng thư giữ nguyên giá trị mới nhưng
        không còn gì giải thích vì sao nó đổi.
        """
        for am in self:
            if am.state == 'applied':
                raise UserError(_(
                    'Không xoá được phụ lục "%(n)s" đã áp dụng cho chứng '
                    'thư %(g)s. Muốn đảo thay đổi thì lập phụ lục mới.',
                    n=am.name, g=am.guarantee_id.name or ''))
        return super().unlink()

    def action_apply(self):
        for am in self:
            if am.state != 'draft':
                raise UserError(_("Phụ lục này đã được áp dụng."))
            g = am.guarantee_id
            if g.state not in ('issued', 'extended'):
                raise UserError(_(
                    "Chỉ áp dụng phụ lục cho BL Đã phát hành / Đã gia hạn."))
            t = am.amendment_type
            if t == 'extension':
                am.value_old = am._fmt_date(g.date_expiry)
                am.value_new = am._fmt_date(am.new_date_expiry)
                g.date_expiry = am.new_date_expiry
                g.state = 'extended'
            elif t == 'amount':
                am.value_old = '{:,.0f}'.format(g.amount)
                am.value_new = '{:,.0f}'.format(am.new_amount)
                g.amount = am.new_amount
            elif t == 'beneficiary':
                am.value_old = g.beneficiary_partner_id.name or ''
                am.value_new = am.new_beneficiary_partner_id.name or ''
                g.beneficiary_partner_id = am.new_beneficiary_partner_id
            elif t == 'cancel':
                g.state = 'released'
                g.date_released = fields.Date.context_today(am)
                g.release_reason = _('Huỷ qua phụ lục %s') % am.name
            am.state = 'applied'
            g.message_post(body=_(
                "Áp dụng phụ lục %(n)s (%(t)s): %(o)s → %(v)s",
                n=am.name,
                t=dict(self._fields['amendment_type'].selection).get(t),
                o=am.value_old or '—', v=am.value_new or '—'))
