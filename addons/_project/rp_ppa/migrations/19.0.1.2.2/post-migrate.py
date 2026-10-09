# -*- coding: utf-8 -*-
"""Tính lại đồng tiền của kỳ sản lượng theo hợp đồng.

Trường ``currency_id`` đổi từ mặc-định-cứng-đô-la sang trường tính theo
hợp đồng mua bán điện. Odoo CHỈ tính trường lưu cho dòng có cột rỗng tại
lúc tạo cột — cột này đã đầy giá trị cũ, nên hàm tính sẽ không bao giờ
chạy. Phải gọi thẳng.

Không xoá cột về rỗng trước: không cần, và gọi trực tiếp thì hàm tính
ghi đè luôn.
"""
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    K = env['rp.energy.period']
    ks = K.search([])
    ks._compute_currency()
    ks.flush_recordset(['currency_id'])
