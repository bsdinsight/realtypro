# -*- coding: utf-8 -*-
"""Nhu cầu vốn dự án (§3) — chuỗi ① đến ⑧.

Hai chỗ đã sai trong quá trình làm và cần khoá lại:
  • Vốn tự có tính trên BAC thì phải trừ phần CÒN PHẢI GÓP, không trừ
    cả số phải góp — phần đã góp nằm sẵn trong chi phí đã thực hiện
    (AC) nên trừ cả tổng là trừ hai lần.
  • Tạm ứng đã chi cho thầu phụ LÀM GIẢM nhu cầu vay (⑥), có lúc bị
    viết thành cộng thêm.
"""
from odoo.tests import tagged

from .common import BorrowingBaseCommon


@tagged('post_install', '-at_install', 're_loan_borrowing_base')
class TestProjectFunding(BorrowingBaseCommon):

    def _sheet(self, **vals):
        base = {'project_id': self.project.id}
        base.update(vals)
        return self.env['re.loan.project.funding'].create(base)

    # ------------------------------------------------------------------
    def test_nhu_cau_von_khong_bao_gio_am(self):
        """Nguồn có sẵn lớn hơn chi phí còn lại → ⑤ = 0, không âm."""
        sheet = self._sheet(supplier_credit=999_000_000_000.0)
        self.assertEqual(sheet.funding_need, 0.0)

    def test_von_tu_co_tren_bac_tru_phan_con_phai_gop(self):
        """Đã góp đủ thì không được trừ tiếp vào nhu cầu vay.

        Góp đủ ⇒ CÒN PHẢI GÓP = 0 ⇒ ② không làm giảm ⑤ nữa; số đã góp
        đã nằm trong AC nên CTC đã tự nhỏ đi rồi.
        """
        sheet = self._sheet(equity_rate_pct=20.0, equity_base='bac')
        required = sheet.equity_required
        sheet.equity_contributed = required
        sheet.invalidate_recordset()
        self.assertEqual(sheet.equity_to_contribute, 0.0)
        self.assertTrue(sheet.equity_ok)
        self.assertEqual(sheet.equity_shortfall, 0.0)

    def test_thieu_von_tu_co_bat_co(self):
        sheet = self._sheet(equity_rate_pct=20.0)
        sheet.equity_contributed = 0.0
        sheet.invalidate_recordset()
        if sheet.equity_required:
            self.assertFalse(sheet.equity_ok)
            self.assertGreater(sheet.equity_shortfall, 0.0)

    def test_cong_no_ncc_lam_giam_nhu_cau_vay(self):
        """④ khai tay tăng ⇒ ⑤ giảm đúng bằng chừng đó (khi chưa chạm 0)."""
        sheet = self._sheet()
        sheet.cost_excluded = 0.0
        before = sheet.funding_need
        sheet.supplier_credit = 1_000_000_000.0
        sheet.invalidate_recordset()
        after = sheet.funding_need
        self.assertAlmostEqual(
            before - after, min(before, 1_000_000_000.0), delta=1.0)

    def test_unfunded_need_tru_du_no_da_giai_ngan(self):
        """⑧ = ⑤ − dư nợ đã rút, không bao giờ âm (ví dụ §9.7)."""
        sheet = self._sheet()
        self._note(5_000_000_000.0)
        sheet.invalidate_recordset()
        self.assertGreaterEqual(sheet.unfunded_need, 0.0)
        self.assertAlmostEqual(
            sheet.unfunded_need,
            max(0.0, sheet.funding_need - sheet.limit_used), delta=1.0)

    def test_du_no_theo_du_an_dung_trong_phieu(self):
        """Dư nợ dự án khác không được cộng vào phiếu của dự án này."""
        sheet = self._sheet()
        self._note(5_000_000_000.0, project=self.project, name='KW-P1')
        self._note(7_000_000_000.0, project=self.project2, name='KW-P2')
        sheet.invalidate_recordset()
        self.assertAlmostEqual(
            sheet.limit_used, 5_000_000_000.0, delta=1.0)
