# -*- coding: utf-8 -*-
"""Dòng tiền dự án & DSCR (§8).

Khoá lại quyết định thiết kế quan trọng nhất của phần này: chỉ tiêu đi
theo DSCR TOÀN KỲ, còn rủi ro thanh khoản đo bằng SỐ DƯ TIỀN LUỸ KẾ.
Dùng DSCR tháng thấp nhất thì dự án nào cũng đỏ, vì tiền xây lắp về theo
đợt nghiệm thu trong khi gốc + lãi đến hạn hàng tháng.
"""
from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.tests import tagged

from .common import BorrowingBaseCommon


@tagged('post_install', '-at_install', 're_loan_borrowing_base')
class TestCashflowDscr(BorrowingBaseCommon):

    def _cashflow(self, months=12):
        cf = self.env['re.loan.project.cashflow']._get_or_create(
            self.project)
        cf.horizon_months = months
        return cf

    def _milestone(self, amount, month_offset):
        first = fields.Date.context_today(self.env.user).replace(day=1)
        return self.env['rp.owner.payment.milestone'].create({
            'contract_id': self.owner_contract.id,
            'name': 'Đợt +%s' % month_offset, 'amount': amount,
            'due_date': first + relativedelta(months=month_offset, days=3)})

    # ------------------------------------------------------------------
    def test_tien_giai_ngan_vay_khong_vao_cfads(self):
        """Vay 20 tỷ mà không có đợt thu nào → CFADS vẫn 0."""
        self._note(20_000_000_000.0)
        cf = self._cashflow()
        cf.action_generate()
        self.assertEqual(
            sum(cf.line_ids.mapped('amount_in')), 0.0,
            'tiền vay là nguồn TÀI TRỢ, không được tính là dòng thu')

    def test_so_du_luy_ke_giu_tien_dot_truoc_cho_thang_sau(self):
        """Thu 10 tỷ tháng 1, chi 1 tỷ tháng 3 → tháng 3 vẫn dương."""
        self._milestone(10_000_000_000.0, 0)
        cf = self._cashflow()
        cf.action_generate()
        lines = cf.line_ids.sorted('date_start')
        self.assertAlmostEqual(
            lines[0].cash_balance, 10_000_000_000.0, delta=1.0)
        self.assertAlmostEqual(
            lines[2].cash_balance, 10_000_000_000.0, delta=1.0,
            msg='tiền thu đợt trước phải được giữ lại cho các tháng sau')
        self.assertEqual(cf.month_cash_short, 0)

    def test_dscr_toan_ky_khong_phai_thang_thap_nhat(self):
        """Thu dồn 1 đợt, nợ rải đều: toàn kỳ đủ nhưng có tháng âm."""
        self._milestone(40_000_000_000.0, 6)
        self._note(20_000_000_000.0)
        cf = self._cashflow()
        cf.action_generate()
        self.assertGreater(
            cf.dscr_overall, 1.0,
            'cả kỳ thu 40 tỷ, nợ ~22 tỷ → DSCR toàn kỳ phải > 1')
        self.assertLess(
            cf.dscr_min, 1.0,
            'các tháng trước đợt thu không có tiền → DSCR tháng < 1')
        self.assertGreater(
            cf.month_cash_short, 0,
            'trước khi đợt thu về thì số dư luỹ kế phải âm')

    def test_khong_co_no_den_han_thi_khong_tinh_dscr(self):
        """Kỳ không có gốc/lãi đến hạn không được kéo DSCR xuống 0."""
        self._milestone(5_000_000_000.0, 1)
        cf = self._cashflow()
        cf.action_generate()
        self.assertEqual(cf.total_debt_service, 0.0)
        self.assertEqual(cf.dscr_overall, 0.0)
        self.assertEqual(cf.month_below_count, 0)

    def test_kw_da_du_an_chia_no_theo_ty_trong(self):
        """KW không gắn dự án, giải ngân 2 dự án → chia đôi nghĩa vụ."""
        note = self.env['re.loan.note'].create({
            'name': 'KW-2DA', 'facility_id': self.fac.id,
            'amount': 20_000_000_000.0, 'date_note': '2026-01-01',
            'tenor_months': 12, 'interest_rate': 10.0})
        note.action_activate()
        self.assertAlmostEqual(
            note._project_share(self.project), 0.0, delta=0.001,
            msg='KW chưa khai dự án và chưa giải ngân → tỷ trọng 0')
        note.project_id = self.project
        self.assertAlmostEqual(
            note._project_share(self.project), 1.0, delta=0.001)
        self.assertAlmostEqual(
            note._project_share(self.project2), 0.0, delta=0.001)
