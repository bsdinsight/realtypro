# -*- coding: utf-8 -*-
"""Việc 1571 — net-off trên kỳ khi tiền trả THẲNG VÀO KỲ (nút "Thanh toán").

Trước đây nút Net-off chỉ có đường ra cho tiền đến từ giấy báo ngân hàng:
trả thừa qua phiếu chi thì kỳ đọc "Đã trả" mà không có nút, trả thiếu đúng
phần phí thì kỳ mắc ở "Trả một phần" cũng không có nút.
"""
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 're_loan')
class TestNetOffPeriod(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['ir.config_parameter'].sudo().set_param(
            're_loan.net_off_threshold', '100000.0')
        cls.bank = cls.env['res.partner'].create({
            'name': 'NH 1571', 'is_company': True, 'is_bank': True})
        cls.contract = cls.env['re.loan.credit.contract'].create({
            'name': 'HĐTD-1571', 'partner_id': cls.bank.id,
            'amount_total': 10_000_000_000.0})
        cls.contract.action_activate()
        cls.fac = cls.env['re.loan.facility'].create({
            'name': 'F-1571', 'credit_contract_id': cls.contract.id,
            'facility_type': 'term', 'amount_limit': 10_000_000_000.0,
            'interest_rate_default': 10.0})
        cls.note = cls.env['re.loan.note'].create({
            'name': 'KW-1571', 'facility_id': cls.fac.id,
            'amount': 1_200_000_000.0, 'date_note': '2026-01-01',
            'tenor_months': 12, 'interest_rate': 10.0,
            'interest_method': 'declining',
            'repayment_plan': 'equal_principal'})
        cls.note.action_activate()
        cls.period = cls.note.interest_line_ids.sorted('period_no')[0]

    def _pay(self, principal=None, interest=None, fee=None):
        """Lập phiếu như nút "Thanh toán": mặc định đúng số còn phải trả."""
        period = self.period
        vals = {
            'note_id': self.note.id, 'date': '2026-02-01',
            'interest_line_id': period.id,
            'amount_principal': (period.amount_principal_remaining
                                 if principal is None else principal),
            'amount_interest': (period.amount_interest_remaining
                                if interest is None else interest),
            'amount_fee': (period.amount_fee_remaining
                           if fee is None else fee),
        }
        rep = self.env['re.loan.note.repayment'].create(vals)
        self.period.invalidate_recordset()
        return rep

    def _net_off(self):
        self.period.action_auto_net_off_period()
        self.period.invalidate_recordset()

    # ----- Trả THỪA --------------------------------------------------------
    def test_tra_thua_trong_nguong_co_nut(self):
        """Vòng 2: kỳ thừa tiền chưa net-off là kỳ chưa khép — "Trả một
        phần", giống chiều thiếu."""
        self._pay(interest=self.period.interest_amount + 50_000.0)
        self.assertEqual(self.period.state, 'partial_paid')
        self.assertTrue(self.period.net_off_allowed)

    def test_net_off_chieu_thua_dong_khoan_du(self):
        rep = self._pay(interest=self.period.interest_amount + 50_000.0)
        paid_before = rep.amount_interest
        n_before = len(self.period.repayment_ids)
        self.assertEqual(self.period.state, 'partial_paid')
        self._net_off()
        self.assertAlmostEqual(
            self.period.amount_over_net_off, 50_000.0, delta=1)
        self.assertFalse(self.period.net_off_allowed, 'đã hết chỗ net-off')
        self.assertEqual(self.period.state, 'paid')
        # Cột "Trích dư" giữ số: nó ghi nhận đã từng thu dư bao nhiêu
        self.assertAlmostEqual(self.period.amount_overpaid, 50_000.0, delta=1)
        # Chứng từ tiền thật không bị sửa, cũng không đẻ thêm dòng trả nợ
        self.assertEqual(rep.amount_interest, paid_before)
        self.assertEqual(len(self.period.repayment_ids), n_before)
        # "Tiền net-off" chỉ đếm dòng ghi bù — hai chiều không trộn lẫn
        self.assertEqual(self.period.amount_net_off, 0.0)

    def test_tra_thua_vuot_nguong_khong_co_nut(self):
        self._pay(interest=self.period.interest_amount + 500_000.0)
        self.assertFalse(self.period.net_off_allowed)
        with self.assertRaises(UserError):
            self.period.action_auto_net_off_period()

    def test_bam_lan_hai_bao_khong_con_chenh_lech(self):
        self._pay(interest=self.period.interest_amount + 50_000.0)
        self._net_off()
        with self.assertRaises(UserError):
            self.period.action_auto_net_off_period()

    def test_xoa_phieu_du_sau_net_off_tra_lai_so(self):
        rep = self._pay(interest=self.period.interest_amount + 50_000.0)
        self._net_off()
        rep.unlink()
        self.period.invalidate_recordset()
        self.assertEqual(self.period.amount_over_net_off, 0.0)
        # Lần sau trả dư thật thì nút phải hiện lại, không bị số cũ trừ mất
        self._pay(interest=self.period.interest_amount + 30_000.0)
        self.assertTrue(self.period.net_off_allowed)

    def test_giam_phieu_du_sau_net_off_giam_theo(self):
        rep = self._pay(interest=self.period.interest_amount + 50_000.0)
        self._net_off()
        rep.amount_interest = self.period.interest_amount + 20_000.0
        self.period.invalidate_recordset()
        self.assertAlmostEqual(
            self.period.amount_over_net_off, 20_000.0, delta=1)
        # Phần dư còn lại đã nằm trọn trong số đã net-off → kỳ vẫn khép
        self.assertEqual(self.period.state, 'paid')

    def test_tra_thua_vuot_nguong_van_tra_mot_phan(self):
        """Thừa quá ngưỡng: không net-off được, kỳ vẫn treo ở "Trả một
        phần" để người dùng thấy mà sửa chứng từ."""
        self._pay(interest=self.period.interest_amount + 500_000.0)
        self.assertEqual(self.period.state, 'partial_paid')
        self.assertFalse(self.period.net_off_allowed)

    def test_sua_phieu_thua_ve_dung_so_thi_da_tra(self):
        rep = self._pay(interest=self.period.interest_amount + 500_000.0)
        rep.amount_interest = self.period.interest_amount
        self.period.invalidate_recordset()
        self.assertEqual(self.period.state, 'paid')

    def test_chi_con_thua_thi_khong_cho_thanh_toan_them(self):
        """Kỳ "Trả một phần" vì thừa: không còn gì để trả, nút Thanh
        toán phải chặn thay vì mở phiếu 0 đồng."""
        self._pay(interest=self.period.interest_amount + 50_000.0)
        with self.assertRaises(UserError):
            self.period.action_create_repayment()

    def test_ky_cu_da_tra_ma_thua_tinh_lai_thanh_tra_mot_phan(self):
        """Giống migration 116: kỳ lưu "Đã trả" theo luật cũ, tính lại
        thì về "Trả một phần"."""
        self._pay(interest=self.period.interest_amount + 50_000.0)
        self.period.state = 'paid'
        self.env.add_to_compute(
            self.period._fields['state'], self.period)
        self.period.flush_recordset()
        self.period.invalidate_recordset()
        self.assertEqual(self.period.state, 'partial_paid')

    # ----- Trả THIẾU -------------------------------------------------------
    def test_tra_thieu_lai_co_nut_va_ve_da_tra(self):
        self._pay(interest=self.period.interest_amount - 50_000.0)
        self.assertEqual(self.period.state, 'partial_paid')
        self.assertTrue(self.period.net_off_allowed)
        self._net_off()
        self.assertEqual(self.period.state, 'paid')
        self.assertAlmostEqual(self.period.amount_net_off, 50_000.0, delta=1)
        self.assertFalse(self.period.net_off_allowed)

    def test_tra_thieu_vuot_nguong_khong_co_nut(self):
        self._pay(interest=self.period.interest_amount - 500_000.0)
        self.assertFalse(self.period.net_off_allowed)
        with self.assertRaises(UserError):
            self.period.action_auto_net_off_period()

    def test_thieu_dung_phan_phi_co_nut_va_ve_da_tra(self):
        """Kẹt cũ: thiếu đúng phần phí thì không có nút, kỳ không về được
        "Đã trả" dù gốc và lãi đã đủ."""
        self.period.fee_amount = 30_000.0
        self.period.invalidate_recordset()
        self._pay(fee=0.0)
        self.assertEqual(self.period.state, 'partial_paid')
        self.assertTrue(self.period.net_off_allowed)
        self._net_off()
        self.assertEqual(self.period.state, 'paid')
        net = self.period.repayment_ids.filtered('is_net_off')
        self.assertAlmostEqual(net.amount_fee, 30_000.0, delta=1)
        self.assertAlmostEqual(net.amount_net_off, 30_000.0, delta=1)

    def test_thieu_ca_lai_lan_phi_net_off_mot_lan(self):
        self.period.fee_amount = 30_000.0
        self.period.invalidate_recordset()
        self._pay(interest=self.period.interest_amount - 20_000.0, fee=0.0)
        self.assertTrue(self.period.net_off_allowed)
        self._net_off()
        self.assertEqual(self.period.state, 'paid')
        self.assertAlmostEqual(self.period.amount_net_off, 50_000.0, delta=1)

    # ----- Thiếu gốc, thừa lãi trên cùng một kỳ ----------------------------
    def test_thieu_goc_thua_lai_mot_lan_bam_dong_ca_hai(self):
        self._pay(principal=self.period.principal_due - 40_000.0,
                  interest=self.period.interest_amount + 20_000.0)
        self.assertTrue(self.period.net_off_allowed)
        self._net_off()
        self.assertEqual(self.period.state, 'paid')
        self.assertAlmostEqual(self.period.amount_net_off, 40_000.0, delta=1)
        self.assertAlmostEqual(
            self.period.amount_over_net_off, 20_000.0, delta=1)
        self.assertFalse(self.period.net_off_allowed)

    def test_mot_chieu_vuot_nguong_thi_khong_ghi_gi(self):
        """Thiếu trong ngưỡng nhưng thừa vượt ngưỡng: nút ẩn, và gọi trực
        tiếp thì báo lỗi TRƯỚC khi ghi dòng bù nào."""
        self._pay(principal=self.period.principal_due - 40_000.0,
                  interest=self.period.interest_amount + 300_000.0)
        self.assertFalse(self.period.net_off_allowed)
        n_before = len(self.period.repayment_ids)
        with self.assertRaises(UserError):
            self.period.action_auto_net_off_period()
        self.period.invalidate_recordset()
        self.assertEqual(len(self.period.repayment_ids), n_before)
        self.assertEqual(self.period.amount_over_net_off, 0.0)

    # ----- Không có gì để net-off ------------------------------------------
    def test_tra_khop_khong_co_nut(self):
        self._pay()
        self.assertEqual(self.period.state, 'paid')
        self.assertFalse(self.period.net_off_allowed)
        with self.assertRaises(UserError):
            self.period.action_auto_net_off_period()

    def test_nguong_bang_0_tat_ca_hai_chieu(self):
        self.env['ir.config_parameter'].sudo().set_param(
            're_loan.net_off_threshold', '0.0')
        self._pay(interest=self.period.interest_amount + 50_000.0)
        self.assertFalse(self.period.net_off_allowed)
        with self.assertRaises(UserError):
            self.period.action_auto_net_off_period()
