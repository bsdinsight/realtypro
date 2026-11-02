# -*- coding: utf-8 -*-
"""Khế ước còn Nháp / Đã gửi NH thì "Đã giải ngân" phải bằng 0 (việc 1584).

Ô này là trường tính có lưu. Đổi công thức không làm Odoo tính lại các bản
ghi đã có, nên khế ước cũ vẫn giữ số đã cộng từ dòng giải ngân tới khi ai
đó sửa nó. Khế ước đã kích hoạt trở đi vẫn đúng, không đụng tới.
"""


def migrate(cr, version):
    cr.execute("""
        UPDATE re_loan_note
           SET amount_disbursed = 0
         WHERE state IN ('draft', 'sent_to_bank')
           AND COALESCE(amount_disbursed, 0) <> 0
    """)
