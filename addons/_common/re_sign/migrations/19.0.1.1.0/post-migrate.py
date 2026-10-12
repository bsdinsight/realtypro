# -*- coding: utf-8 -*-
"""Dựng `res_model_id` từ mã model đã cất ở pre-migrate."""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    cr.execute("""
        SELECT EXISTS (SELECT 1 FROM information_schema.tables
                       WHERE table_name = 're_approval_rule_model_bak')
    """)
    if not cr.fetchone()[0]:
        return
    # Nối theo mã model. Luật trỏ tới model không còn tồn tại thì để
    # nguyên rỗng — xoá đi là mất cấu hình người dùng đã khai, mà để lại
    # thì họ còn nhìn thấy và tự quyết.
    cr.execute("""
        UPDATE re_approval_rule r
           SET res_model_id = m.id,
               res_model    = m.model
          FROM re_approval_rule_model_bak b
          JOIN ir_model m ON m.model = b.res_model
         WHERE r.id = b.id
    """)
    _logger.info('re_sign: đã nối %s luật phê duyệt sang ir.model', cr.rowcount)
    cr.execute("""
        SELECT count(*) FROM re_approval_rule WHERE res_model_id IS NULL
    """)
    con = cr.fetchone()[0]
    if con:
        _logger.warning(
            're_sign: %s luật phê duyệt không nối được model — để trống '
            'cho người dùng tự xử lý, KHÔNG xoá.', con)
    # Ghi bằng SQL thô thì hàm tính của trường TÍNH-CÓ-LƯU không hề
    # chạy — `is_signable` sẽ nằm im ở False và cả màn cấu hình báo sai
    # rằng chưa chứng từ nào bật ký. Phải gọi tính lại tường minh.
    from odoo import api, SUPERUSER_ID
    env = api.Environment(cr, SUPERUSER_ID, {})
    luat = env['re.approval.rule'].search([])
    if luat:
        luat._compute_is_signable()
        luat.flush_recordset(['is_signable'])
        _logger.info('re_sign: đã tính lại cờ "đã bật ký" cho %s luật',
                     len(luat))

    cr.execute("DROP TABLE re_approval_rule_model_bak")
