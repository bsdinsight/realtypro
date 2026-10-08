# -*- coding: utf-8 -*-
"""Mẫu thư nhắc bảo lãnh hết hạn: tắt "người nhận mặc định".

Từ Odoo 19, `mail.template.use_default_to` mặc định True. Khi bật,
Odoo BỎ QUA ô "To (Emails)" của mẫu và lấy người nhận từ bản ghi —
chứng thư bảo lãnh không có partner nào để lấy, nên thư đi mà không có
địa chỉ nhận: người phụ trách khai đủ ngày nhắc vẫn không nhận được gì
(việc 1452).

Mẫu thư nằm trong khối `noupdate="1"` (để giữ phần thân khách đã sửa),
nên khai lại trong XML không áp cho bản đã cài — phải sửa thẳng ở đây.
"""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    template = env.ref('re_guarantee.mail_template_guarantee_expiry',
                       raise_if_not_found=False)
    if not template:
        return
    vals = {}
    if template.use_default_to:
        vals['use_default_to'] = False
    # Mẫu cũ có thể còn thiếu ô người nhận nếu khách từng xoá tay.
    if not template.email_to and not template.partner_to:
        vals['email_to'] = '{{ object.pic_user_id.email_formatted }}'
    if vals:
        template.write(vals)
