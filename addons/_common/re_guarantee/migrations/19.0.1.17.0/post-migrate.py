# -*- coding: utf-8 -*-
"""Tính lại hạn mức đã sử dụng của các hạn mức bảo lãnh.

Bản này đổi ĐỊNH NGHĨA của "đã sử dụng": đề nghị BL kích hoạt không
còn chiếm hạn mức, còn chứng thư BỊ THU thì vẫn chiếm.

`amount_used` là trường compute STORE. Đổi thân hàm tính không làm
Odoo ghi lại giá trị đã lưu — nó chỉ tính lại khi có phụ thuộc thay
đổi. Không có bước này thì mọi hạn mức bảo lãnh giữ nguyên con số
tính theo quy tắc CŨ cho tới khi ai đó vô tình chạm vào một chứng
thư, và trong khoảng đó phần mềm hiển thị hạn mức khả dụng sai.
"""


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID
    env = api.Environment(cr, SUPERUSER_ID, {})
    Facility = env['re.loan.facility']
    facs = Facility.search([('purpose', '=', 'bank_guarantee')])
    if not facs:
        return
    for fname in ('guarantee_total_outstanding',
                  'guarantee_request_outstanding',
                  'amount_used', 'amount_available'):
        field = Facility._fields.get(fname)
        if field is not None and field.store and field.compute:
            env.add_to_compute(field, facs)
    env.flush_all()
