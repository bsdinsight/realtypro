# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 're_loan_borrowing_base')
class TestCollateralAdvanceRate(TransactionCase):
    """Việc 1414: tỷ lệ cho vay phải thấy ngay trên tài sản bảo đảm,
    không phải mở danh mục loại tài sản mới biết."""

    def test_rate_and_lendable_value_on_collateral(self):
        ctype = self.env['re.loan.collateral.type'].create({
            'name': 'BĐS thử 1414', 'advance_rate': 70.0})
        col = self.env['re.loan.collateral'].create({
            'name': 'Nhà xưởng thử', 'type_id': ctype.id})
        self.env['re.loan.collateral.valuation'].create({
            'collateral_id': col.id, 'amount': 10_000_000_000.0})
        col.invalidate_recordset(['value_current'])
        self.assertEqual(col.advance_rate, 70.0)
        self.assertAlmostEqual(col.value_lendable, 7_000_000_000.0, places=2)
        # Đổi tỷ lệ ở loại tài sản thì tài sản đi theo.
        ctype.advance_rate = 50.0
        col.invalidate_recordset(['advance_rate', 'value_lendable'])
        self.assertAlmostEqual(col.value_lendable, 5_000_000_000.0, places=2)

    def test_columns_present_on_collateral_views(self):
        for view in ('list', 'form'):
            arch = self.env['re.loan.collateral'].get_views(
                [(False, view)])['views'][view]['arch']
            self.assertIn('advance_rate', arch, view)
            self.assertIn('value_lendable', arch, view)
