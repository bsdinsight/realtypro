# -*- coding: utf-8 -*-
from odoo import _, api, fields, models


class EamOutage(models.Model):
    """Chiều ngược: một khoảng dừng cần những lệnh công việc nào.

    Quan hệ là MỘT-NHIỀU, và theo chiều này mới đúng. Một lần dừng dài
    thường sinh nhiều lệnh nối nhau — chẩn đoán, rồi sửa, rồi chạy thử.
    Gộp cả ba vào một lệnh thì mất dấu phần lớn thời gian đã đi đâu, mà
    đó chính là phần cần soi.

    Và ô ``has_work_order`` để lọc ra các khoảng dừng **không có lệnh
    nào**. Đừng coi đó là lỗi: khởi động lại từ xa là một lần dừng thật,
    không có hành động bảo trì nào. Nhưng một khoảng dừng DÀI mà không
    có lệnh công việc thì đúng là chỗ cần hỏi.
    """
    _inherit = 'eam.outage'

    work_order_ids = fields.One2many(
        'eam.work.order', 'outage_id', string='Lệnh công việc')
    work_order_count = fields.Integer(
        string='Số lệnh công việc', compute='_compute_wo', store=True)
    has_work_order = fields.Boolean(
        string='Có lệnh công việc', compute='_compute_wo', store=True,
        help='Khoảng dừng không có lệnh nào KHÔNG phải lỗi — khởi động '
             'lại từ xa là một lần dừng thật mà không có hành động bảo '
             'trì. Nhưng khoảng dừng DÀI mà không có lệnh thì nên hỏi.')
    wo_cost_total = fields.Monetary(
        string='Chi phí can thiệp', compute='_compute_wo', store=True,
        help='Giờ công, vật tư và thuê ngoài của các lệnh gắn vào khoảng '
             'dừng này. Cộng với doanh thu tổn thất mới ra tiền thật.')

    @api.depends('work_order_ids.cost_total', 'work_order_ids.state')
    def _compute_wo(self):
        for o in self:
            ds = o.work_order_ids.filtered(
                lambda w: w.state != 'cancelled')
            o.work_order_count = len(ds)
            o.has_work_order = bool(ds)
            o.wo_cost_total = sum(ds.mapped('cost_total'))

    def action_tao_lenh(self):
        """Mở form lệnh công việc mới cho khoảng dừng này."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Lệnh công việc mới'),
            'res_model': 'eam.work.order',
            'view_mode': 'form',
            'context': {
                'default_outage_id': self.id,
                'default_location_id': self.location_id.id,
                'default_asset_id': self.asset_id.id,
                'default_work_type': (
                    'corrective' if self.counts_as_downtime else 'inspection'),
            },
        }

    def action_mo_lenh(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Lệnh công việc — %s', self.display_name),
            'res_model': 'eam.work.order',
            'view_mode': 'list,form',
            'domain': [('outage_id', '=', self.id)],
            'context': {'default_outage_id': self.id,
                        'default_location_id': self.location_id.id},
        }
