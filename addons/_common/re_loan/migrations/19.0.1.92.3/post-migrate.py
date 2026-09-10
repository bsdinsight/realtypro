# -*- coding: utf-8 -*-
"""Tính lại cột "Tiền net-off" của lịch lãi theo nguồn mới.

Trường vẫn là `amount_net_off`/`has_net_off` như cũ nên Odoo KHÔNG tự
tính lại khi chỉ thân hàm compute đổi — số cũ (đọc từ giấy báo ngân
hàng) sẽ nằm lại trong cột dù công thức đã khác. Ép tính lại toàn bộ.

Lưu ý về dữ liệu cũ: định nghĩa mới chỉ cộng các dòng trả nợ ĐƯỢC ĐÁNH
DẤU net-off, mà cờ đó bắt đầu được ghi từ bản này trở đi. Nên các kỳ
net-off từ trước sẽ về 0 cho tới khi có thao tác net-off mới. Cố ý:
cờ cũ đánh dấu cả những dòng thu tiền thật chỉ vì dòng giấy báo của
chúng có một khoản lẻ — gán nhầm loại còn tệ hơn để trống.
"""
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Line = env['re.loan.note.interest.line']
    lines = Line.search([])
    if not lines:
        return
    for fname in ('amount_net_off', 'has_net_off'):
        env.add_to_compute(Line._fields[fname], lines)
    lines.flush_recordset(['amount_net_off', 'has_net_off'])
