# -*- coding: utf-8 -*-
"""Giữ lại mã model cũ trước khi `res_model` thành trường liên quan.

`res_model` đổi từ Selection (người dùng chọn) thành trường LIÊN QUAN
suy từ `res_model_id`. Ngay khi module nạp xong, Odoo sẽ tính lại cột đó
từ `res_model_id` — lúc này còn rỗng — và ghi đè mất giá trị cũ. Nên
phải cất sang một bảng tạm ở pre-migrate, rồi post-migrate mới dựng lại
liên kết.
"""


def migrate(cr, version):
    if not version:
        return
    cr.execute("""
        SELECT EXISTS (SELECT 1 FROM information_schema.columns
                       WHERE table_name = 're_approval_rule'
                         AND column_name = 'res_model')
    """)
    if not cr.fetchone()[0]:
        return
    cr.execute("DROP TABLE IF EXISTS re_approval_rule_model_bak")
    cr.execute("""
        CREATE TABLE re_approval_rule_model_bak AS
        SELECT id, res_model FROM re_approval_rule
         WHERE res_model IS NOT NULL
    """)
