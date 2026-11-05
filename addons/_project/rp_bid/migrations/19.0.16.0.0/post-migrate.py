# -*- coding: utf-8 -*-
"""Tính lại hai chỗ đổi cách tính VAT.

1. `rp.bid.item.unit_price_offer` nay theo "Gốc VAT của biểu giá" khai ở
   hồ sơ. Hồ sơ cũ CHƯA khai gốc nên ô này về 0 — cố ý: không ai biết
   mẫu biểu giá của từng gói cũ ghi chưa VAT hay đã gồm VAT, và đoán là
   cách lỗi cũ sinh ra. Người làm hồ sơ khai gốc thì số hiện lại.
2. `rp.bid.price.library_price` nay quy về giá chưa VAT.

KHÔNG sửa đơn giá trong các dòng chi phí đã có (`rp.bid.resource.line`).
Đó có thể là giá người làm giá đã sửa tay; dòng nào từng kéo nguyên giá
"đã gồm VAT" từ công bố thì phải rà và kéo lại — xem tin nhắn khi bấm
"Lấy chi phí từ định mức".
"""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    Item = env['rp.bid.item']
    Price = env['rp.bid.price']
    items = Item.with_context(active_test=False).search([])
    prices = Price.with_context(active_test=False).search([])
    env.add_to_compute(Item._fields['unit_price_offer'], items)
    env.add_to_compute(Price._fields['library_price'], prices)
    env.flush_all()
