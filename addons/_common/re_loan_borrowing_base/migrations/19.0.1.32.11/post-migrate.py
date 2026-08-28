# -*- coding: utf-8 -*-
"""Chuyển TSBĐ gắn thẳng facility sang bảng phân bổ.

Trước phiên bản này, base của một mục đích = Σ pledge có
`pledge_target='facility'` trỏ vào nó. Nay base = Σ dòng PHÂN BỔ. Không
chuyển thì mọi mục đích đang có TSBĐ riêng tụt về 0 sau khi nâng cấp —
số đúng biến mất mà không ai biết vì sao.

Pledge cấp HĐTD KHÔNG tự chia: chia thế nào là quyết định nghiệp vụ,
đoán hộ là sai tiền. Chúng nằm ở phần "Chưa phân bổ" cho tới khi người
dùng vào chia.
"""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    Alloc = env['re.loan.pledge.allocation']

    pledges = env['re.loan.collateral.pledge'].search([
        ('pledge_target', '=', 'facility'),
        ('facility_id', '!=', False),
    ])
    vals = []
    for p in pledges:
        if Alloc.search_count([('pledge_id', '=', p.id),
                               ('facility_id', '=', p.facility_id.id)]):
            continue
        if not p.base_contribution:
            continue
        vals.append({
            'pledge_id': p.id,
            'facility_id': p.facility_id.id,
            'amount': p.base_contribution,
            'note': 'Chuyển tự động khi nâng cấp — TSBĐ vốn gắn riêng '
                    'mục đích này.',
        })
    if vals:
        Alloc.create(vals)
