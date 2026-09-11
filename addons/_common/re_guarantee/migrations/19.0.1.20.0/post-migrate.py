# -*- coding: utf-8 -*-
"""Đề nghị BL đã kích hoạt chiếm hạn mức trở lại (backlog 732).

Bản 19.0.1.17.0 bỏ đề nghị ra khỏi "đã sử dụng"; người dùng cuối chốt
ngược lại: kích hoạt là giữ chỗ ngay, không chờ phát hành chứng thư.

`amount_used` là trường compute CÓ LƯU — đổi thân hàm không làm Odoo
ghi lại giá trị đã nằm trong bảng. Không ép tính lại thì mọi hạn mức
bảo lãnh giữ con số theo quy tắc CŨ cho tới khi có ai vô tình chạm vào
một đề nghị, và trong khoảng đó phần mềm cho phát hành vượt phần thực
còn.

Quét theo `purpose_kind` chứ KHÔNG theo `purpose = 'bank_guarantee'`
như bản migration trước: từ backlog 730 mục đích là danh mục người
dùng tự khai, mục tự khai thuộc nhóm Bảo lãnh cũng chiếm hạn mức.
"""
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Facility = env['re.loan.facility']
    facs = Facility.search([('purpose_kind', '=', 'guarantee')])
    if not facs:
        return
    for fname in ('guarantee_total_outstanding',
                  'guarantee_request_outstanding',
                  'amount_used', 'amount_available'):
        field = Facility._fields.get(fname)
        if field is not None and field.store and field.compute:
            env.add_to_compute(field, facs)
    env.flush_all()
