# -*- coding: utf-8 -*-
"""Migrate 12 field bảo lãnh phẳng trên rp.contract → bản ghi
rp.contract.guarantee (chạy 1 lần khi cài module).

Các field phẳng (guarantee_performance_* / advance_* / warranty_*) là
placeholder do rp_contract ship trước. Đọc chúng, tạo bản ghi tương
ứng, KHÔNG xóa cột (giữ an toàn — dọn sau ở bản cleanup riêng).
"""
import logging

from odoo import fields

_logger = logging.getLogger(__name__)

SPECS = [
    ('performance', 'guarantee_performance_no', 'guarantee_performance_bank_id',
     'guarantee_performance_amount', 'guarantee_performance_expiry'),
    ('advance', 'guarantee_advance_no', 'guarantee_advance_bank_id',
     'guarantee_advance_amount', 'guarantee_advance_expiry'),
    ('warranty', 'guarantee_warranty_no', 'guarantee_warranty_bank_id',
     'guarantee_warranty_amount', 'guarantee_warranty_expiry'),
]


def post_init_migrate_flat_guarantees(env):
    Contract = env['rp.contract']
    Guarantee = env['rp.contract.guarantee']
    created = 0
    contracts = Contract.search([])
    for c in contracts:
        for gtype, f_no, f_bank, f_amount, f_expiry in SPECS:
            number = getattr(c, f_no, False)
            amount = getattr(c, f_amount, 0.0)
            expiry = getattr(c, f_expiry, False)
            if not (number or amount or expiry):
                continue
            # tránh tạo trùng nếu chạy lại
            exists = Guarantee.search_count([
                ('contract_id', '=', c.id),
                ('guarantee_type', '=', gtype),
                ('name', '=', number or _placeholder(gtype)),
            ])
            if exists:
                continue
            bank = getattr(c, f_bank, False)
            Guarantee.create({
                'name': number or _placeholder(gtype),
                'guarantee_type': gtype,
                'security_form': 'bank_guarantee',
                'contract_id': c.id,
                'issuer_partner_id': bank.id if bank else False,
                'amount': amount or 0.0,
                'date_expiry': (expiry or c.date_end or c.date_start
                                or fields.Date.context_today(Contract)),
                'state': 'active' if expiry else 'draft',
                'note': 'Chuyển từ field bảo lãnh cũ trên hợp đồng.',
            })
            created += 1
    if created:
        _logger.info(
            "rp_contract_guarantee: migrated %s bảo lãnh phẳng → bản ghi",
            created)


def _placeholder(gtype):
    return {'performance': 'BL-THHĐ',
            'advance': 'BL-TU',
            'warranty': 'BL-BH'}.get(gtype, 'BL')
