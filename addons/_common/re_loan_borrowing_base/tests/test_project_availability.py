# -*- coding: utf-8 -*-
"""Khả dụng theo DỰ ÁN = min() các nhánh — không phải phép cộng.

Công thức này đã bị viết sai và sửa lại nhiều lần: có lúc rút thành
`phân bổ + base riêng − dư nợ`, tới khi đối chiếu ví dụ §9 của tài liệu
khách hàng mới thấy sai (ra 500 thay vì 0). Bộ test này khoá lại đúng
hành vi min(), kèm hai cột chẩn đoán `blocked_by` / `unlock_gap`.
"""
from odoo.tests import tagged

from .common import BorrowingBaseCommon


@tagged('post_install', '-at_install', 're_loan_borrowing_base')
class TestProjectAvailability(BorrowingBaseCommon):

    def _alloc(self, amount, facility=None, project=None):
        return self.env['re.loan.facility.project.allocation'].create({
            'facility_id': (facility or self.fac).id,
            'project_id': (project or self.project).id,
            'amount': amount})

    # ------------------------------------------------------------------
    def test_han_muc_chan_khi_chua_co_tsbd(self):
        """Không pledge nào → nhánh chặn là hạn mức phân bổ cho dự án.

        `blocked_by` chỉ ra nhánh THẤP NHẤT, kể cả khi mọi thứ bình
        thường; 'none' chỉ xuất hiện khi các nhánh bằng nhau. Đây là
        thông tin "đang bị cái gì giới hạn", không phải cờ lỗi.
        """
        alloc = self._alloc(10_000_000_000.0)
        self.assertAlmostEqual(
            alloc.amount_available_project, 10_000_000_000.0, delta=1.0)
        self.assertEqual(alloc.blocked_by, 'limit')

    def test_tsbd_thap_hon_han_muc_thi_tsbd_chan(self):
        """base riêng dự án 4 tỷ < phân bổ 10 tỷ → khả dụng = 4 tỷ.

        Đây là ca mà công thức cộng sẽ ra sai: 10 + 4 − 0 = 14 tỷ.
        """
        col = self._make_collateral(8_000_000_000.0, 50.0)   # base 4 tỷ
        self._pledge(col, 8_000_000_000.0, target='facility')
        alloc = self._alloc(10_000_000_000.0)
        self.assertAlmostEqual(
            alloc.amount_available_project, 4_000_000_000.0, delta=1.0)
        self.assertEqual(alloc.blocked_by, 'collateral')

    def test_du_no_tru_vao_khap_moi_nhanh(self):
        """Rút 3 tỷ: hạn mức còn 7, TSBĐ còn 1 → min = 1 tỷ."""
        col = self._make_collateral(8_000_000_000.0, 50.0)
        self._pledge(col, 8_000_000_000.0, target='facility')
        alloc = self._alloc(10_000_000_000.0)
        self._note(3_000_000_000.0)
        alloc.invalidate_recordset()
        self.assertAlmostEqual(
            alloc.amount_available_project, 1_000_000_000.0, delta=1.0)

    def test_khong_bao_gio_am(self):
        """Dư nợ vượt base → khả dụng phải là 0, không phải số âm."""
        col = self._make_collateral(2_000_000_000.0, 50.0)   # base 1 tỷ
        self._pledge(col, 2_000_000_000.0, target='facility')
        alloc = self._alloc(10_000_000_000.0)
        self._note(5_000_000_000.0)
        alloc.invalidate_recordset()
        self.assertEqual(alloc.amount_available_project, 0.0)
        self.assertTrue(self.fac.margin_call,
                        'dư nợ vượt base riêng phải bật margin call')

    def test_unlock_gap_la_khoang_cach_toi_nhanh_ke_tiep(self):
        """Gỡ được nhánh đang chặn thì khả dụng lên tới đâu.

        Phân bổ 3 tỷ trong khi TSBĐ đỡ được 4 tỷ ⇒ nhánh chặn là hạn
        mức, nới phân bổ thì được thêm 1 tỷ nữa (tới trần TSBĐ).
        """
        col = self._make_collateral(8_000_000_000.0, 50.0)   # base 4 tỷ
        self._pledge(col, 8_000_000_000.0, target='facility')
        alloc = self._alloc(3_000_000_000.0)
        self.assertEqual(alloc.blocked_by, 'limit')
        self.assertAlmostEqual(
            alloc.amount_available_project, 3_000_000_000.0, delta=1.0)
        self.assertAlmostEqual(
            alloc.unlock_gap, 1_000_000_000.0, delta=1.0)

    def test_du_an_khac_khong_an_ke_han_muc_cua_nhau(self):
        """Dư nợ dự án A không được làm tụt khả dụng dự án B."""
        a = self._alloc(10_000_000_000.0)
        b = self._alloc(10_000_000_000.0, project=self.project2)
        self._note(6_000_000_000.0, project=self.project, name='KW-A')
        a.invalidate_recordset()
        b.invalidate_recordset()
        self.assertAlmostEqual(
            a.amount_available_project, 4_000_000_000.0, delta=1.0)
        self.assertAlmostEqual(
            b.amount_available_project, 10_000_000_000.0, delta=1.0)
