# -*- coding: utf-8 -*-
"""Đánh dấu lại "Có net-off" cho các kỳ bị trích dư (backlog 988).

Bản này mở rộng nghĩa của cờ: ngoài "có dòng trả nợ net-off", kỳ bị
NGÂN HÀNG TRÍCH DƯ cũng được đánh dấu.

`has_net_off` là trường tính toán CÓ LƯU — đổi thân hàm không làm Odoo
ghi lại giá trị đã nằm trong bảng. Không ép tính lại thì đúng những kỳ
đang trích dư (thứ mà việc này sinh ra để nhìn thấy) lại là những kỳ
KHÔNG được đánh dấu, cho tới khi có ai vô tình chạm vào một dòng trả
nợ của kỳ đó.
"""
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Line = env['re.loan.note.interest.line']
    lines = Line.search([])
    if not lines:
        return
    for fname in ('amount_overpaid', 'has_net_off'):
        field = Line._fields.get(fname)
        if field is not None and field.store and field.compute:
            env.add_to_compute(field, lines)
    lines.flush_recordset()
