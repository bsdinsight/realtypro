# -*- coding: utf-8 -*-
"""Điền các trường mới cho dữ liệu đang có.

1. `rp.bid.resource.line.source_norm_id` (việc 1381) — dòng chi phí cũ
   không ghi nguồn. Suy ra CHỈ KHI chắc: tài nguyên có trong định mức
   đang chọn của dòng BoQ VỚI ĐÚNG hao phí đó. Dòng như vậy chính là nội
   dung của định mức, đổi định mức thì bỏ là đúng. Dòng không khớp (nhập
   từ file dự toán, sửa tay) để trống nguồn — không bao giờ tự xoá.
2. Tính lại các trường lưu mới: số lượng tài nguyên (việc 1411), cờ ĐVT
   lệch định mức (việc 1383), cờ "của định mức cũ", và KL ta bóc được
   của dòng chào (nay so ĐVT theo tên đã chuẩn hoá).
"""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    if not version:
        return
    cr.execute("""
        UPDATE rp_bid_resource_line rl
           SET source_norm_id = bl.norm_id
          FROM rp_bid_boq_line bl, rp_norm_line nl
         WHERE rl.line_id = bl.id
           AND bl.norm_id IS NOT NULL
           AND rl.source_norm_id IS NULL
           AND nl.norm_id = bl.norm_id
           AND nl.resource_id = rl.resource_id
           AND abs(coalesce(nl.quantity, 0) - coalesce(rl.norm_qty, 0)) < 1e-9
           AND coalesce(nl.is_percent, false) = coalesce(rl.is_percent, false)
    """)
    env = api.Environment(cr, SUPERUSER_ID, {})
    RL = env['rp.bid.resource.line']
    Line = env['rp.bid.boq.line']
    Item = env['rp.bid.item']
    Bid = env['rp.bid']
    rls = RL.search([])
    env.add_to_compute(RL._fields['resource_qty'], rls)
    env.add_to_compute(RL._fields['norm_stale'], rls)
    env.add_to_compute(Line._fields['uom_mismatch'], Line.search([]))
    env.flush_all()
    # Dòng chào: cùng một hàm tính cả "KL ta bóc được" lẫn thành tiền chào.
    # Tính lại hết để chữa các dòng giữ số cũ do thiếu phụ thuộc
    # `bid_id.offer_total` (xem rp_bid_item.py), RỒI mới tính lại phần đối
    # soát của hồ sơ — chênh bảng chào đọc tổng các dòng chào.
    env.add_to_compute(Item._fields['takeoff_quantity'], Item.search([]))
    env.flush_all()
    env.add_to_compute(Bid._fields['offer_gap'],
                       Bid.with_context(active_test=False).search([]))
    env.flush_all()
