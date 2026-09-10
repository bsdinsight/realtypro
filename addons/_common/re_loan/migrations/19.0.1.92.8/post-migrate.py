# -*- coding: utf-8 -*-
"""Tính lại cờ "Hiệu lực hồi tố" trên phụ lục lãi suất (backlog 737).

Trước đây là ô tick tay; nay hệ thống tự suy ra từ ngày hiệu lực và
trạng thái các kỳ lãi. Trường có store nên phải ép tính lại, không thì
phụ lục cũ giữ nguyên cờ tick tay (thường là chưa tick) và nút "Tính
chênh lệch" vẫn bị ẩn đúng như tình huống khách đang gặp.
"""
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Amendment = env['re.loan.note.amendment']
    recs = Amendment.search([('amendment_type', '=', 'rate')])
    if not recs:
        return
    env.add_to_compute(Amendment._fields['is_retroactive'], recs)
    recs.flush_recordset(['is_retroactive'])
