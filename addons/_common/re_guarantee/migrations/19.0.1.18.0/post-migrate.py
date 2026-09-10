# -*- coding: utf-8 -*-
"""Tính lại phí / ký quỹ / phạt của Đề nghị PHBL theo chứng thư.

Từ bản này, đề nghị đã phát hành lấy các số PHẢI TRẢ từ chứng thư chứ
không tự tính nữa (backlog 727). Các trường đó đều store nên Odoo
không tự tính lại khi chỉ thân hàm compute đổi — không ép thì số cũ
nằm nguyên và "còn phải trả" vẫn lệch đúng như khách báo.
"""
from odoo import api, SUPERUSER_ID

FIELDS = [
    'guarantee_fee_amount', 'deposit_amount', 'penalty_amount',
    'penalty_days', 'total_due',
    'guarantee_fee_paid', 'guarantee_fee_remaining',
    'deposit_paid', 'deposit_remaining',
    'penalty_paid', 'penalty_remaining',
    'total_paid', 'is_fully_paid',
]


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Request = env['re.guarantee.request']
    reqs = Request.search([])
    if not reqs:
        return
    for fname in FIELDS:
        field = Request._fields.get(fname)
        if field and field.store and field.compute:
            env.add_to_compute(field, reqs)
    reqs.flush_recordset()
