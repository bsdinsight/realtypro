# -*- coding: utf-8 -*-
"""KW "Đã gửi NH" thôi chiếm hạn mức — tính lại toàn bộ (backlog 716).

Trước bản này, khế ước vừa bấm "Gửi ngân hàng" là đã trừ ngay vào "Đã
sử dụng" của mục đích. Sai: gửi hồ sơ mới là bước nội bộ, ngân hàng
chưa ký nhận nợ nên chưa có đồng nào ra. Nay chỉ KÍCH HOẠT mới chiếm
hạn mức.

`amount_used`, `amount_available` (hạn mức) và `aging_bucket` (khế ước)
đều là trường tính toán CÓ LƯU — đổi thân hàm không làm Odoo tính lại
giá trị đã nằm trong bảng, nên phải ép ở đây. Không ép thì mọi hạn mức
đang có KW "Đã gửi NH" vẫn giữ số cũ: hạn mức bị chiếm oan cho tới khi
có gì đó chạm vào KW.

`amount_pending_bank` là cột mới nên Odoo tự tính khi thêm cột, không
cần liệt kê.
"""
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})

    Facility = env['re.loan.facility']
    facilities = Facility.search([])
    if facilities:
        for fname in ('amount_used', 'amount_available'):
            field = Facility._fields.get(fname)
            if field is not None and field.store and field.compute:
                env.add_to_compute(field, facilities)
        facilities.flush_recordset()

    Note = env['re.loan.note']
    notes = Note.search([('state', '=', 'sent_to_bank')])
    if notes:
        field = Note._fields.get('aging_bucket')
        if field is not None and field.store and field.compute:
            env.add_to_compute(field, notes)
        notes.flush_recordset()
