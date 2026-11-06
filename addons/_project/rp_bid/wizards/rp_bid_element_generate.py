# -*- coding: utf-8 -*-
"""Tạo cấu kiện cho hồ sơ từ danh mục loại cấu kiện (việc 1404).

Hỏi MỖI LOẠI BAO NHIÊU CÁI rồi sinh từng cái — xem docstring của
`rp.bid.element.type` vì sao danh mục là loại chứ không phải từng cái.
Mã cấu kiện sinh theo tiền tố của hồ sơ (`rp.bid.element.create`); tên
là tên loại kèm số thứ tự TIẾP THEO số cấu kiện cùng loại đã có, nên bấm
thêm lần nữa không đẻ ra tên trùng.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class RpBidElementGenerate(models.TransientModel):
    _name = 'rp.bid.element.generate'
    _description = 'Tạo cấu kiện cho hồ sơ dự thầu'

    bid_id = fields.Many2one('rp.bid', string='Hồ sơ dự thầu', required=True)
    element_prefix = fields.Char(
        related='bid_id.element_prefix', string='Tiền tố mã cấu kiện')
    line_ids = fields.One2many(
        'rp.bid.element.generate.line', 'wizard_id', string='Loại cấu kiện')

    @api.model
    def default_get(self, fields_list):
        """Đổ sẵn mọi loại đang dùng, số lượng 0 — chỉ việc gõ số."""
        res = super().default_get(fields_list)
        if 'line_ids' in fields_list:
            types = self.env['rp.bid.element.type'].search([])
            res['line_ids'] = [(0, 0, {'type_id': t.id, 'quantity': 0})
                               for t in types]
        return res

    def action_generate(self):
        self.ensure_one()
        Element = self.env['rp.bid.element']
        todo = self.line_ids.filtered(lambda l: l.quantity > 0)
        if not todo:
            raise UserError(_('Chưa nhập số lượng cho loại cấu kiện nào.'))
        vals_list = []
        for line in todo:
            start = Element.with_context(active_test=False).search_count([
                ('bid_id', '=', self.bid_id.id),
                ('type_id', '=', line.type_id.id)])
            for i in range(1, line.quantity + 1):
                vals_list.append({
                    'bid_id': self.bid_id.id,
                    'type_id': line.type_id.id,
                    'name': _('%(name)s số %(no)s',
                              name=line.type_id.name, no=start + i),
                })
        Element.create(vals_list)
        return self.bid_id.action_open_elements()


class RpBidElementGenerateLine(models.TransientModel):
    _name = 'rp.bid.element.generate.line'
    _description = 'Dòng tạo cấu kiện'

    wizard_id = fields.Many2one(
        'rp.bid.element.generate', required=True, ondelete='cascade')
    type_id = fields.Many2one(
        'rp.bid.element.type', string='Loại cấu kiện', required=True)
    category = fields.Selection(related='type_id.category')
    quantity = fields.Integer(string='Số lượng', default=0)

    @api.constrains('quantity')
    def _check_quantity(self):
        for rec in self:
            if rec.quantity < 0:
                raise UserError(_('Số lượng cấu kiện không được âm.'))
