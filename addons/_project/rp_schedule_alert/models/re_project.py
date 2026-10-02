# -*- coding: utf-8 -*-
"""Ngưỡng cảnh báo đặt theo DỰ ÁN, không đặt chung một chỗ.

Dự án nhà ở 18 tháng và dự án điện 3 năm không thể chung một ngưỡng "còn
5 ngày dư địa là báo động". Để mỗi dự án tự chỉnh, mặc định hợp lý sẵn.
"""
from odoo import _, api, fields, models


class ReProject(models.Model):
    _inherit = 're.project'

    alert_ids = fields.One2many(
        'rp.schedule.alert', 'project_id', string='Cảnh báo tiến độ')
    alert_open_count = fields.Integer(
        string='Cảnh báo đang mở', compute='_compute_alert_stats')
    alert_critical_count = fields.Integer(
        string='Cảnh báo nghiêm trọng', compute='_compute_alert_stats')

    alert_float_days = fields.Integer(
        string='Ngưỡng dư địa (ngày)', default=5,
        help='Báo khi công việc còn dư địa toàn dự án ÍT HƠN hoặc bằng '
             'số ngày này. Dư địa âm luôn là mức nghiêm trọng.')
    alert_slip_days = fields.Integer(
        string='Ngưỡng trượt kế hoạch gốc (ngày)', default=7,
        help='Báo khi công việc chưa xong mà đã kết thúc muộn hơn kế '
             'hoạch gốc từng này ngày trở lên.')
    alert_interface_days = fields.Integer(
        string='Ngưỡng dư địa điểm giao (ngày)', default=0,
        help='Báo khi điểm giao còn dư địa ÍT HƠN hoặc bằng số ngày này. '
             'Để 0 nghĩa là chỉ báo khi đã mâu thuẫn.')

    @api.depends('alert_ids.state', 'alert_ids.severity')
    def _compute_alert_stats(self):
        for rec in self:
            op = rec.alert_ids.filtered(
                lambda a: a.state in ('open', 'acknowledged'))
            rec.alert_open_count = len(op)
            rec.alert_critical_count = len(
                op.filtered(lambda a: a.severity == 'critical'))

    def action_scan_alerts(self):
        self.ensure_one()
        created, updated, resolved = self.env['rp.schedule.alert']._scan_project(self)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'warning' if created else 'success',
                'message': _(
                    'Quét xong: %(n)s cảnh báo mới, %(u)s còn nguyên, '
                    '%(r)s đã hết.',
                    n=len(created), u=len(updated), r=len(resolved)),
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }

    def action_open_alerts(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Cảnh báo tiến độ — %s', self.name),
            'res_model': 'rp.schedule.alert',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'search_default_f_open': 1},
        }
