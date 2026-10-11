# -*- coding: utf-8 -*-
"""Tính lại chi phí thực sau khi hàm tính biết quy đổi tiền tệ.

``rp.structure.actual_cost`` là trường tính-CÓ-LƯU. Đổi thân hàm tính
không làm Odoo tính lại: cột đã có giá trị thì giá trị cũ nằm đó mãi,
nên hạng mục nào có hoá đơn ghi bằng tiền khác hạng mục sẽ giữ nguyên
con số chưa quy đổi cho tới khi có ai sửa một dòng hoá đơn.

Gọi thẳng hàm tính, KHÔNG xoá cột về NULL trước — ``actual_cost`` là
Monetary, đặt NULL trên cột đang có ràng buộc sẽ nổ, mà cũng không cần:
hàm tính ghi đè toàn bộ giá trị.
"""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    hang_muc = env['rp.structure'].search([])
    if not hang_muc:
        return
    hang_muc._compute_actual_cost()
    hang_muc.flush_recordset(['actual_cost'])

    import logging
    logging.getLogger(__name__).info(
        'rp_cost_actual: tính lại chi phí thực cho %d hạng mục '
        '(đã quy đổi tiền tệ theo chứng từ).', len(hang_muc))
