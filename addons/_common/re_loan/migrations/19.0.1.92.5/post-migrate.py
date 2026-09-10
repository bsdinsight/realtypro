# -*- coding: utf-8 -*-
"""Tính lại "Hạn mức còn lại" cho MỌI hạn mức.

Bản 19.0.1.92.4 lỡ làm mất @api.depends của `_compute_amount_available`:
khi thêm cột "Tổng HM khả dụng" (backlog 718), phần khai depends của
hàm cũ bị hàm mới nuốt mất. Hậu quả: hạn mức tạo mới sau bản đó có
`amount_available` = NULL, đọc ra 0 → tạo khế ước là báo "vượt hạn mức
còn lại (0.0)" dù hạn mức còn nguyên. Hạn mức cũ thì đứng im ở số
trước đó, không cập nhật theo dư nợ nữa.

Depends đã trả lại. Chỗ này ép tính lại toàn bộ vì trường có store —
sửa thân hàm/khai depends không làm Odoo tự tính lại giá trị đã nằm
trong bảng.
"""
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Facility = env['re.loan.facility']
    facilities = Facility.search([])
    if not facilities:
        return
    for fname in ('amount_used', 'amount_available',
                  'amount_limit_purpose'):
        field = Facility._fields.get(fname)
        if field is not None and field.store and field.compute:
            env.add_to_compute(field, facilities)
    facilities.flush_recordset()
