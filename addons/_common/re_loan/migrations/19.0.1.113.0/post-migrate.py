# -*- coding: utf-8 -*-
""""Đã giải ngân" không còn cộng các dòng giải ngân đã huỷ (việc 1595).

Ô này là trường tính có lưu nên đổi công thức không tính lại bản ghi cũ. Chỉ
sửa khế ước có dòng đã huỷ. Khế ước Nháp / Đã gửi NH vốn bằng 0, bỏ qua.

KHÔNG sửa "Số tiền KW" của dữ liệu cũ: ô đó có thể đã được người dùng nhập tay
hoặc đã dựng lịch lãi theo nó, không suy lại được từ các dòng giải ngân.
"""


def migrate(cr, version):
    cr.execute("""
        UPDATE re_loan_note n
           SET amount_disbursed = COALESCE((
                   SELECT SUM(d.amount)
                     FROM re_loan_note_disbursement d
                    WHERE d.note_id = n.id
                      AND d.state <> 'cancelled'), 0)
         WHERE n.state NOT IN ('draft', 'sent_to_bank')
           AND EXISTS (
                   SELECT 1
                     FROM re_loan_note_disbursement c
                    WHERE c.note_id = n.id
                      AND c.state = 'cancelled')
    """)
