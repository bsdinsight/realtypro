# -*- coding: utf-8 -*-
"""Recompute BAC (estimate_value) + % tiến độ sau khi thêm lớp BOQ.

v1.18.0 đổi compute của estimate_value: giờ = boq_total or estimate_total
(BAC ưu tiên Dự toán BOQ, else Khái toán). Compute cũ dùng
``@api.depends()`` rỗng nên estimate_value của các structure hiện có chưa
từng được tính lại → thường = 0 dù đã có Khái toán, khiến progress_percent
(chia cho estimate_value) sai. Migration này force recompute một lần cho
toàn bộ hạng mục để dữ liệu cũ đúng ngay sau upgrade.
"""
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    structs = env['rp.structure'].search([])
    if not structs:
        return
    # Thứ tự: boq_total → estimate_value (BAC) → progress (dùng BAC).
    structs._compute_boq_total()
    structs._compute_estimate_value()
    structs._compute_progress()
    env.flush_all()
