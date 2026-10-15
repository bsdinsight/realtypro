# -*- coding: utf-8 -*-
"""Nối ngược từ lệnh công việc về cảnh báo — vòng phải khép hai đầu.

Cầu một chiều là cầu hỏng. Cảnh báo sinh ra lệnh, nhưng lệnh xong mà
cảnh báo vẫn nằm đó mở thì sau một tháng sổ cảnh báo toàn dòng mồ côi,
và không ai đọc nữa. Nên đóng lệnh là **khép cảnh báo**, và lần khép đó
chính là mốc để đo tái phát.

Một chỗ cố ý không tự động: cờ ``clear_on_wo_done`` cho phép TẮT việc
tự khép. Dùng cho cảnh báo phải tự hết bằng số đo trở lại bình thường —
sửa xong mà độ rung vẫn cao thì chưa sửa được, và việc hệ thống tuyên bố
"đã hết" vì có người bấm đóng lệnh là nói sai.
"""
from odoo import _, api, fields, models


class EamWorkOrder(models.Model):
    _inherit = 'eam.work.order'

    alarm_ids = fields.One2many(
        'eam.alarm', 'wo_id', string='Cảnh báo đã gộp')
    alarm_count = fields.Integer(string='Số cảnh báo',
                                 compute='_compute_alarm')
    alarm_repeat_max = fields.Integer(
        string='Tái phát nhiều nhất', compute='_compute_alarm',
        help='Cảnh báo trong lệnh này đã tái phát bao nhiêu lần sau sửa. '
             'Lớn hơn 0 nghĩa là lần sửa trước không giữ được — làm lại y '
             'như cũ thì kết quả sẽ y như cũ.')

    @api.depends('alarm_ids.repeat_after_fix')
    def _compute_alarm(self):
        for o in self:
            o.alarm_count = len(o.alarm_ids)
            o.alarm_repeat_max = max(
                o.alarm_ids.mapped('repeat_after_fix') or [0])

    def _khep_canh_bao(self):
        """Khép các cảnh báo mà lệnh này xử lý."""
        gio = fields.Datetime.now()
        for o in self:
            for a in o.alarm_ids.filtered(lambda x: x.state == 'wo'):
                if a.rule_id and not a.rule_id.clear_on_wo_done:
                    a.message_post(body=_(
                        'Lệnh %s đã xong, nhưng luật cảnh báo đặt là phải '
                        'tự hết bằng số đo. Cảnh báo giữ nguyên tới khi trị '
                        'số về trong ngưỡng.', o.name))
                    continue
                a.write({'state': 'cleared', 'date_cleared': gio})
                # `_()` của Odoo KHÔNG cho vừa tham số vị trí vừa tham số
                # tên — nó assert, và lỗi nổ ở tận lúc đóng lệnh.
                a.message_post(body=_(
                    'Khép theo lệnh %(l)s. Nếu cảnh báo này nổ lại trong '
                    '%(n)d ngày tới, nó sẽ được đếm là TÁI PHÁT.',
                    l=o.name, n=(a.rule_id.repeat_window_days
                                 if a.rule_id else 30)))
        return True

    def action_xong(self):
        res = super().action_xong()
        self._khep_canh_bao()
        return res

    def action_huy(self):
        res = super().action_huy()
        # Huỷ lệnh thì cảnh báo phải QUAY LẠI trạng thái cần xử lý, không
        # được nằm mãi ở "đã có lệnh" — lệnh đó không còn tồn tại.
        for o in self:
            for a in o.alarm_ids.filtered(lambda x: x.state == 'wo'):
                a.write({'state': 'ack'})
                a.message_post(body=_(
                    'Lệnh %s đã huỷ. Cảnh báo quay về cần xử lý.', o.name))
        return res

    def action_mo_canh_bao(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Cảnh báo — %s', self.name),
            'res_model': 'eam.alarm',
            'view_mode': 'list,form',
            'domain': [('wo_id', '=', self.id)],
        }
