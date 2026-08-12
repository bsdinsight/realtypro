# -*- coding: utf-8 -*-
"""Bộ khung dữ liệu dùng chung cho test borrowing base."""
from odoo.tests import TransactionCase


class BorrowingBaseCommon(TransactionCase):
    """Dựng sẵn: 1 dự án · 1 HĐTD · 2 facility · 1 HĐ với CĐT."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.project = cls.env['re.project'].create(
            {'name': 'BB-Test', 'code': 'BBT'})
        cls.project2 = cls.env['re.project'].create(
            {'name': 'BB-Test-2', 'code': 'BBT2'})
        cls.bank = cls.env['res.partner'].create(
            {'name': 'NH-BB', 'is_company': True, 'is_bank': True})
        cls.owner = cls.env['res.partner'].create(
            {'name': 'CĐT-BB', 'is_company': True})
        cls.credit = cls.env['re.loan.credit.contract'].create({
            'name': 'HĐTD-BB', 'partner_id': cls.bank.id,
            'amount_total': 100_000_000_000.0})
        cls.credit.action_activate()
        cls.fac = cls.env['re.loan.facility'].create({
            'name': 'F-BB', 'credit_contract_id': cls.credit.id,
            'facility_type': 'revolving',
            'amount_limit': 60_000_000_000.0})
        cls.fac2 = cls.env['re.loan.facility'].create({
            'name': 'F-BB-2', 'credit_contract_id': cls.credit.id,
            'facility_type': 'revolving',
            'amount_limit': 40_000_000_000.0})
        cls.owner_contract = cls.env['rp.owner.contract'].create({
            'name': 'HĐ-CĐT-BB', 'project_id': cls.project.id,
            'owner_id': cls.owner.id,
            'contract_value_pretax': 200_000_000_000.0})

    # ------------------------------------------------------------------
    @classmethod
    def _make_collateral(cls, value, rate):
        """TSBĐ đã định giá + loại có tỷ lệ cho vay `rate` %."""
        ctype = cls.env['re.loan.collateral.type'].create({
            'name': 'Loại-%s' % rate, 'code': 'LT%s' % int(rate * 100),
            'advance_rate': rate})
        col = cls.env['re.loan.collateral'].create({
            'name': 'TS-%s' % int(value), 'type_id': ctype.id})
        cls.env['re.loan.collateral.valuation'].create({
            'collateral_id': col.id, 'date': '2026-01-01',
            'amount': value})
        return col

    @classmethod
    def _pledge(cls, collateral, secured, target='contract', facility=None):
        return cls.env['re.loan.collateral.pledge'].create({
            'collateral_id': collateral.id, 'pledge_target': target,
            'credit_contract_id': cls.credit.id,
            'facility_id': (facility or cls.fac).id
            if target in ('facility', 'note') else False,
            'secured_amount': secured, 'date_pledge': '2026-01-01',
            'state': 'active'})

    @classmethod
    def _note(cls, amount, facility=None, project=None, name='KW-BB'):
        note = cls.env['re.loan.note'].create({
            'name': name, 'facility_id': (facility or cls.fac).id,
            'amount': amount, 'date_note': '2026-01-01',
            'tenor_months': 12, 'interest_rate': 10.0,
            'project_id': (project or cls.project).id})
        note.action_activate()
        return note
