# -*- coding: utf-8 -*-
"""Tính lại "Trích dư" sau khi kẹp sàn nghĩa vụ (backlog 988 vòng 4).

Bản 19.0.1.98.0 đã tính lại một lần, nhưng khi đó công thức chưa kẹp
sàn 0 cho nghĩa vụ của kỳ. Kỳ có `principal_due` ÂM (nhập tay sai) vì
thế đọc ra "trích dư" đúng bằng phần âm đó dù chưa trả đồng nào.

Mỗi lần đổi thân hàm của trường CÓ LƯU là một lần phải ép tính lại —
không gộp được vào migration cũ vì bản cũ đã chạy trên các máy đã cập
nhật.
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
