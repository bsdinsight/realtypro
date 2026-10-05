# -*- coding: utf-8 -*-
"""Quan hệ trước–sau: m2m phẳng → rp.task.link (FS, lệch 0).

Bảng m2m cũ `rp_task_predecessor_rel` không mang nổi loại quan hệ và độ
lệch. Chuyển từng dòng thành một quan hệ FS lệch 0 — đúng nghĩa dữ liệu
cũ, không đoán thêm gì. Chỉ xoá bảng cũ khi đã đối chiếu đủ số dòng.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

# Chèn bằng SQL thì các field tính-và-lưu (dự án, hợp đồng, độ lệch thực
# tế, cờ vi phạm) KHÔNG được tính — chúng nằm lại NULL và mọi con số đếm
# theo dự án đều thiếu. Phải xếp lại vào hàng đợi tính toán.
_COMPUTED = ('project_id', 'contract_id', 'pred_contract_id',
             'is_cross_contract', 'lag_actual', 'lag_gap', 'is_violated')


def migrate(cr, version):
    cr.execute("""
        SELECT 1 FROM information_schema.tables
         WHERE table_name = 'rp_task_predecessor_rel'
    """)
    if not cr.fetchone():
        return
    cr.execute('SELECT count(*) FROM rp_task_predecessor_rel')
    before = cr.fetchone()[0]
    if not before:
        cr.execute('DROP TABLE rp_task_predecessor_rel')
        return
    # Bỏ cặp tự trỏ và cặp trùng — ràng buộc của model mới không nhận.
    cr.execute("""
        INSERT INTO rp_task_link
            (task_id, predecessor_id, link_type, lag_days,
             create_uid, write_uid, create_date, write_date)
        SELECT DISTINCT r.task_id, r.pred_id, 'FS', 0,
               1, 1, now(), now()
          FROM rp_task_predecessor_rel r
          JOIN project_task s ON s.id = r.task_id
          JOIN project_task p ON p.id = r.pred_id
         WHERE r.task_id <> r.pred_id
           AND NOT EXISTS (
               SELECT 1 FROM rp_task_link l
                WHERE l.task_id = r.task_id
                  AND l.predecessor_id = r.pred_id)
    """)
    moved = cr.rowcount
    cr.execute("""
        SELECT count(*) FROM rp_task_predecessor_rel r
          JOIN project_task s ON s.id = r.task_id
          JOIN project_task p ON p.id = r.pred_id
         WHERE r.task_id <> r.pred_id
    """)
    expected = cr.fetchone()[0]
    _logger.info('rp_schedule: chuyển %s/%s quan hệ sang rp.task.link '
                 '(tổng dòng cũ %s)', moved, expected, before)
    if moved >= expected:
        cr.execute('DROP TABLE rp_task_predecessor_rel')
    else:
        _logger.warning('rp_schedule: GIỮ bảng rp_task_predecessor_rel vì '
                        'chưa chuyển đủ — kiểm tra lại trước khi xoá')
    _recompute(cr)


def _recompute(cr):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Link = env['rp.task.link']
    links = Link.search([])
    for name in _COMPUTED:
        env.add_to_compute(Link._fields[name], links)
    links.flush_recordset()
    _logger.info('rp_schedule: đã tính lại %s trường suy ra cho %s quan hệ',
                 len(_COMPUTED), len(links))
