# -*- coding: utf-8 -*-
"""Giao dịch mô phỏng cũ mang nguồn 'sepay' → chuyển sang 'demo_simulate'.

Wizard luôn đặt external_id = 'SIM<epoch ms>'; id SePay thật là số nên
không bao giờ bắt đầu bằng 'SIM'.
"""


def migrate(cr, version):
    cr.execute("""
        UPDATE re_bank_transaction
           SET source = 'demo_simulate'
         WHERE source = 'sepay' AND external_id LIKE 'SIM%'
    """)
