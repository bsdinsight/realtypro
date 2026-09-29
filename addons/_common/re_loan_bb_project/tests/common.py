# -*- coding: utf-8 -*-
"""Khung dữ liệu test cho phần nối borrowing base với thi công.

Dùng lại khung của lõi rồi thêm hợp đồng với CĐT — thứ chỉ có khi cài
bộ thi công.
"""
from odoo.addons.re_loan_borrowing_base.tests.common import (
    BorrowingBaseCommon as CoreCommon,
)


class BorrowingBaseCommon(CoreCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.owner_contract = cls.env['rp.owner.contract'].create({
            'name': 'HĐ-CĐT-BB', 'project_id': cls.project.id,
            'owner_id': cls.owner.id,
            'contract_value_pretax': 200_000_000_000.0})
