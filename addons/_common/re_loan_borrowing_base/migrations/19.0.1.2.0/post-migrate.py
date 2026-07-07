# -*- coding: utf-8 -*-
"""Recompute base_contribution sau khi đổi công thức: cap giá trị tính
base theo định giá mới nhất của TSĐB (min(secured_amount, value_current)
khi TS đã có định giá) — để định giá lại TSĐB lan truyền vào khả dụng
HĐTD/facility kể cả khi pledge đã khai giá trị đảm bảo."""
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    pledges = env['re.loan.collateral.pledge'].search([])
    pledges._compute_base_contribution()
    # Cascade lên base facility + HĐTD (stored)
    env['re.loan.facility'].search([])._compute_borrowing_base()
    env['re.loan.credit.contract'].search(
        [])._compute_borrowing_base_total()
    env.flush_all()
