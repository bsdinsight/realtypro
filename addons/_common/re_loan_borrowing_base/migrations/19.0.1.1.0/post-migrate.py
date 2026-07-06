# -*- coding: utf-8 -*-
"""Recompute base/has_pledges sau khi đổi logic: pledge chưa khai tỷ lệ
(advance_rate=0) không còn kích hoạt ràng buộc base → hết margin call
giả trên dữ liệu có sẵn."""
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['re.loan.facility'].search([])._compute_borrowing_base()
    env['re.loan.credit.contract'].search(
        [])._compute_borrowing_base_total()
    env.flush_all()
