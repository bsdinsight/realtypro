# -*- coding: utf-8 -*-
"""Nối bước trên lệnh ngược về bước trong kế hoạch bảo trì.

Khai ở ĐÂY chứ không ở `eam_work_order`: chiều phụ thuộc là
`eam_pm` → `eam_work_order`, nên tầng dưới không được biết tới
`eam.pm.task`. Khai ngược chiều thì registry không dựng nổi —
"unknown comodel_name".
"""
from odoo import fields, models


class EamWorkOrderStep(models.Model):
    _inherit = 'eam.work.order.step'

    pm_task_id = fields.Many2one(
        'eam.pm.task', string='Bước trong kế hoạch', ondelete='set null',
        index=True,
        help='Truy ngược về kế hoạch đã sinh ra bước này — để biết tiêu '
             'chuẩn lấy từ đâu khi có tranh cãi.')
