# -*- coding: utf-8 -*-
"""Tính lại "Trích dư" cho mọi kỳ lãi (backlog 988 vòng 4).

Bản này mở rộng định nghĩa: "Trích dư" nay gồm CẢ phần ngân hàng trích
cho kỳ mà không rót hết vào kỳ (nằm lại ở giấy báo), chứ không chỉ
phần dòng trả nợ nhập thừa.

`amount_overpaid` và `has_net_off` là trường tính toán CÓ LƯU. Không
ép tính lại thì đúng những kỳ đang có tiền treo ở giấy báo — thứ việc
này sinh ra để nhìn thấy — vẫn đọc là 0.
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
