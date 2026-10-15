# -*- coding: utf-8 -*-
"""Phần biểu mẫu động gắn lên lệnh công việc.

Tách khỏi ``eam_form.py`` vì THỨ TỰ NẠP: file kia định nghĩa mixin
``eam.form.field.mixin``, mà ``eam.work.order.step`` cần mixin đó nên
phải nạp trước nó. Còn lớp mở rộng ``eam.work.order`` thì ngược lại —
phải nạp SAU file định nghĩa model. Để chung một file thì một trong hai
chiều sẽ sai, và lỗi hiện ra là "Model does not exist in registry" chứ
không nói gì về thứ tự.
"""
from odoo import _, api, fields, models


class EamWorkOrder(models.Model):
    _inherit = 'eam.work.order'

    step_auto_fail = fields.Integer(
        string='Bước máy xét KHÔNG ĐẠT', compute='_compute_step_auto',
        help='Số bước mà SỐ ĐO nằm ngoài tiêu chuẩn. Khác với số bước '
             'người làm tự tick không đạt — chỗ lệch giữa hai con số là '
             'chỗ đáng xem.')
    step_auto_mismatch = fields.Integer(
        string='Bước người chấm lệch máy xét',
        compute='_compute_step_auto',
        help='Người làm tick ĐẠT (hoặc chưa làm) trong khi số đo nói '
             'KHÔNG ĐẠT, hoặc ngược lại.')

    @api.depends('step_ids.auto_result', 'step_ids.result')
    def _compute_step_auto(self):
        for o in self:
            b = o.step_ids
            o.step_auto_fail = len(b.filtered(
                lambda s: s.auto_result == 'not_ok'))
            o.step_auto_mismatch = len(b.filtered(
                lambda s: s.auto_result in ('ok', 'not_ok')
                and s.result in ('ok', 'not_ok')
                and s.result != s.auto_result))

    def action_gan_mau_bieu(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Gắn mẫu biểu vào %s', self.name),
            'res_model': 'eam.form.apply.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_wo_id': self.id},
        }
