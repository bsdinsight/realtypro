# -*- coding: utf-8 -*-
"""Backlog 1091: cờ quá hạn của kỳ lãi chưa từng được cron tính lại
theo ngày, nên dữ liệu đang có có thể thiếu kỳ đã trễ. Tính lại một
lần lúc nâng cấp; từ nay cron hằng ngày lo."""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['re.loan.note.interest.line']._refresh_overdue_flags()
