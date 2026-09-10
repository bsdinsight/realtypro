# -*- coding: utf-8 -*-
"""Điều chỉnh ngày kích hoạt khế ước đã kích hoạt.

Ngày kích hoạt là gốc tính lãi, nên nhập sai nó là sai toàn bộ lịch
lãi lẫn ngày thanh toán ghi trên các chứng từ mà khế ước đã trả. Sửa
thẳng vào ô trên form thì lặng lẽ quá: không ai biết vì sao số đổi,
và các chứng từ ngoài phân hệ Vay không được cập nhật theo.

Wizard này bắt khai LÝ DO, ghi vết cũ → mới vào chatter, rồi gọi hook
`_after_activation_date_changed` để các phân hệ khác (hoá đơn, tạm
ứng) cập nhật ngày thanh toán theo.
"""
from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ReLoanNoteActivationDateWizard(models.TransientModel):
    _name = 're.loan.note.activation.date.wizard'
    _description = 'Điều chỉnh ngày kích hoạt khế ước'

    note_id = fields.Many2one(
        're.loan.note', string='Khế ước', required=True,
        ondelete='cascade')
    date_note = fields.Date(
        related='note_id.date_note', string='Ngày nhận nợ',
        readonly=True)
    current_date = fields.Date(
        related='note_id.date_activation', string='Ngày kích hoạt hiện tại',
        readonly=True)
    new_date = fields.Date(
        string='Ngày kích hoạt mới', required=True)
    reason = fields.Char(
        string='Lý do điều chỉnh', required=True,
        help='VD: nhập nhầm ngày, ngân hàng thông báo lại ngày giải '
             'ngân thực tế.')
    impact_note = fields.Char(
        string='Ảnh hưởng', compute='_compute_impact')

    @api.depends('note_id')
    def _compute_impact(self):
        for wiz in self:
            wiz.impact_note = wiz.note_id._activation_date_impact_note()

    @api.constrains('new_date', 'note_id')
    def _check_new_date(self):
        today = fields.Date.context_today(self)
        for wiz in self:
            if not wiz.new_date:
                continue
            if wiz.new_date > today:
                raise UserError(_(
                    'Ngày kích hoạt không được ở tương lai — đây là '
                    'ngày ngân hàng đã kích hoạt trên hồ sơ.'))
            if wiz.note_id.date_note and wiz.new_date < wiz.note_id.date_note:
                raise UserError(_(
                    'Ngày kích hoạt (%(a)s) không được trước Ngày nhận '
                    'nợ (%(b)s).',
                    a=wiz.new_date, b=wiz.note_id.date_note))

    def action_confirm(self):
        self.ensure_one()
        note = self.note_id
        old_date = note.date_activation
        if old_date == self.new_date:
            raise UserError(_('Ngày mới trùng ngày đang có.'))
        # write() của khế ước tự dựng lại lịch lãi cho các kỳ dự kiến.
        note.write({'date_activation': self.new_date})
        note.message_post(body=Markup(_(
            'Điều chỉnh <b>Ngày kích hoạt</b>: %(o)s → <b>%(n)s</b>.'
            '<br/>Lý do: %(r)s')) % {
                'o': old_date or _('(chưa có)'),
                'n': self.new_date,
                'r': self.reason})
        note._after_activation_date_changed(old_date, self.new_date)
        return {'type': 'ir.actions.act_window_close'}
