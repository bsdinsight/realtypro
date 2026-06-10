# -*- coding: utf-8 -*-
"""
Phụ lục HĐ nhà thầu — 6 loại.

Áp dụng ghi giá trị cũ/mới (audit) vào HĐ; với thay đổi trọng yếu (giá trị,
kỳ hạn, lịch trả) hiển thị message lên chatter để theo dõi.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class RpContractAmendment(models.Model):
    _name = 'rp.contract.amendment'
    _description = 'Phụ lục HĐ nhà thầu'
    _inherit = ['mail.thread']
    _order = 'date_effective desc, id desc'

    name = fields.Char(string='Số phụ lục', required=True, copy=False)
    contract_id = fields.Many2one(
        'rp.contract', string='HĐ', required=True, ondelete='cascade',
        index=True, tracking=True)
    amendment_type = fields.Selection(
        [('extension', 'Gia hạn'),
         ('value', 'Thay đổi giá trị HĐ'),
         ('scope', 'Thay đổi phạm vi / khối lượng'),
         ('schedule', 'Thay đổi lịch trả'),
         ('parties', 'Thay đổi thông tin các bên'),
         ('other', 'Khác')],
        string='Loại phụ lục', required=True, tracking=True)
    date_effective = fields.Date(
        string='Ngày hiệu lực', required=True,
        default=fields.Date.context_today)

    new_date_end = fields.Date(string='Ngày hoàn thành mới')
    new_contract_value_pretax = fields.Monetary(string='Giá trị HĐ mới (trước thuế)')
    description = fields.Text(string='Diễn giải', required=True)

    value_old = fields.Char(string='Giá trị cũ', readonly=True)
    value_new = fields.Char(string='Giá trị mới', readonly=True)
    state = fields.Selection(
        [('draft', 'Nháp'), ('applied', 'Đã áp dụng')],
        string='Trạng thái', default='draft', required=True, tracking=True)

    currency_id = fields.Many2one(
        related='contract_id.currency_id', store=True, readonly=True)
    company_id = fields.Many2one(
        related='contract_id.company_id', store=True, readonly=True)

    @api.constrains('amendment_type', 'new_contract_value_pretax')
    def _check_new_values(self):
        for am in self:
            if am.amendment_type == 'value' \
                    and am.new_contract_value_pretax <= 0:
                raise ValidationError(_("Giá trị mới phải > 0."))

    def action_apply(self):
        for am in self:
            if am.state != 'draft':
                raise UserError(_("Phụ lục đã áp dụng."))
            contract = am.contract_id
            if contract.state in ('draft', 'terminated'):
                raise UserError(_(
                    "Chỉ áp dụng phụ lục cho HĐ đã ký / đang thực hiện."))
            t = am.amendment_type
            if t == 'extension':
                if not am.new_date_end:
                    raise UserError(_("Cần nhập Ngày hoàn thành mới."))
                am.value_old = str(contract.date_end or '')
                am.value_new = str(am.new_date_end)
                contract.date_end = am.new_date_end
            elif t == 'value':
                if not am.new_contract_value_pretax:
                    raise UserError(_("Cần nhập Giá trị HĐ mới."))
                am.value_old = '{:,.0f}'.format(contract.contract_value_pretax)
                am.value_new = '{:,.0f}'.format(am.new_contract_value_pretax)
                contract.contract_value_pretax = am.new_contract_value_pretax
            elif t in ('scope', 'schedule', 'parties', 'other'):
                # Chỉ ghi nhận diễn giải (audit qua chatter).
                am.value_old = ''
                am.value_new = (am.description or '')[:200]
            am.state = 'applied'
            contract.message_post(body=_(
                "Áp dụng phụ lục %(name)s (%(type)s): %(d)s",
                name=am.name,
                type=dict(self._fields['amendment_type'].selection).get(t),
                d=am.description or ''))
        return True

    def unlink(self):
        for am in self:
            if am.state == 'applied':
                raise UserError(_(
                    "Không xoá phụ lục đã áp dụng (giữ vết)."))
        return super().unlink()
