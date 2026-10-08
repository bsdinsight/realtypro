# -*- coding: utf-8 -*-
"""Dòng "Điều chỉnh" trong lịch lãi không được mang tiền gốc (việc 1436).

Dòng điều chỉnh sinh từ Thông báo Nợ/Có là khoản truy thu / truy hoàn
LÃI, mang cùng số kỳ với kỳ gốc. Công thức tính tiền gốc trước đây chỉ
nhìn số kỳ nên gán cho nó nguyên tiền gốc của kỳ đó: lịch đòi gốc hai
lần, tổng gốc vượt số tiền khế ước.

Dữ liệu cũ nào đã lỡ lưu tiền gốc trên dòng điều chỉnh thì trả về 0 —
không đụng tới các kỳ lãi thật.
"""


def migrate(cr, version):
    cr.execute("""
        UPDATE re_loan_note_interest_line
           SET principal_due = 0
         WHERE line_type = 'adjustment'
           AND COALESCE(principal_due, 0) <> 0
    """)
