# -*- coding: utf-8 -*-
"""Tính lại phần hạn mức bị bảo lãnh chiếm, sau khi đổi tiêu chí.

Từ bản này, "hạn mức bảo lãnh" nhận diện theo PHÂN LOẠI mục đích
(purpose_kind = guarantee) chứ không theo mã 'bank_guarantee' cứng —
để mục đích tự khai thuộc nhóm Bảo lãnh cũng bị chiếm hạn mức đúng
(backlog 730). `amount_used` có store nên phải ép tính lại.
"""
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Facility = env['re.loan.facility']
    facilities = Facility.search([])
    if not facilities:
        return
    for fname in ('amount_used', 'amount_available'):
        field = Facility._fields.get(fname)
        if field is not None and field.store and field.compute:
            env.add_to_compute(field, facilities)
    facilities.flush_recordset()
