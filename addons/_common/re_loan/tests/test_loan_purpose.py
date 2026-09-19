# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 're_loan')
class TestLoanPurposeCode(TransactionCase):
    """Backlog 1084: tạo mục đích sử dụng vốn không cần khai mã."""

    def test_code_generated_from_name(self):
        Purpose = self.env['re.loan.purpose']
        p1 = Purpose.create({'name': 'Vốn lưu động đặc thù Đường sắt'})
        self.assertEqual(p1.code, 'von_luu_dong_dac_thu_duong_sat')
        # Trùng tên → thêm số đuôi, không vỡ ràng buộc unique.
        p2 = Purpose.create({'name': 'Vốn lưu động đặc thù Đường sắt'})
        self.assertEqual(p2.code, 'von_luu_dong_dac_thu_duong_sat_2')
        # Tên mở đầu bằng số vẫn ra mã hợp lệ (phải bắt đầu bằng chữ).
        p3 = Purpose.create({'name': '2026 — gói đặc biệt'})
        self.assertEqual(p3.code, 'md_2026_goi_dac_biet')
        # Ai truyền mã sẵn (import, data file) thì giữ nguyên.
        p4 = Purpose.create({'name': 'Mục tự đặt mã', 'code': 'custom_x'})
        self.assertEqual(p4.code, 'custom_x')
