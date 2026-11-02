# -*- coding: utf-8 -*-
"""Việc 1594 — Số tiền KW chỉ đọc, tự cộng từ các dòng giải ngân; bấm Gửi NH /
Kích hoạt mà chưa có dòng nào thì báo.

Dùng Form cho phần giao diện: Form giữ đúng luật bỏ ô chỉ đọc khi lưu của web
client, nên thiếu force_save là lộ ra ở đây. Gán thẳng vào ORM thì không.

Form phải chạy bằng người dùng thật: với tài khoản hệ thống (su), Odoo 19 gỡ cả
hai bản khai `loan_type` trên form (một bản theo nhóm, một bản theo phủ định
nhóm), rồi điều kiện readonly của ô số tiền không tính được.
"""
from odoo.exceptions import UserError
from odoo.tests import Form, TransactionCase, tagged
from odoo.tests.common import new_test_user


@tagged('post_install', '-at_install', 're_loan')
class TestNoteAmountFromLines(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bank = cls.env['res.partner'].create({
            'name': 'NH 1594', 'is_company': True, 'is_bank': True})
        cls.contract = cls.env['re.loan.credit.contract'].create({
            'name': 'HĐTD-1594', 'partner_id': cls.bank.id,
            'amount_total': 10_000_000_000.0})
        cls.contract.action_activate()
        cls.fac = cls.env['re.loan.facility'].create({
            'name': 'F-1594', 'credit_contract_id': cls.contract.id,
            'facility_type': 'revolving', 'amount_limit': 5_000_000_000.0,
            'interest_rate_default': 10.0})
        cls.user = new_test_user(
            cls.env, login='user_1594',
            groups='base.group_user,re_loan.group_loan_manager')

    def _note(self, amount, **vals):
        return self.env['re.loan.note'].create({
            'name': 'KW-1594', 'facility_id': self.fac.id,
            'amount': amount, 'date_note': '2026-01-01',
            'tenor_months': 12, 'interest_rate': 10.0,
            'interest_method': 'declining', 'repayment_plan': 'bullet',
            **vals})

    def _line(self, note, amount):
        return self.env['re.loan.note.disbursement'].create({
            'note_id': note.id, 'date': '2026-01-05', 'amount': amount})

    def _add_line_on_form(self, note, amount):
        with Form(note.with_user(self.user)) as form:
            with form.disbursement_ids.new() as line:
                line.amount = amount

    def _button(self, note):
        return note.with_context(check_disbursement_lines=True)

    # ----- Ô Số tiền KW trên form -------------------------------------------
    def test_o_so_tien_chi_doc(self):
        with Form(self._note(0.0).with_user(self.user)) as form:
            with self.assertRaises(AssertionError):
                form.amount = 1_000_000.0

    def test_them_dong_tren_form_luu_dung_so_tong(self):
        note = self._note(0.0)
        self._add_line_on_form(note, 300_000_000.0)
        self.assertEqual(note.amount, 300_000_000.0,
                         'thiếu force_save thì số này không được lưu')
        self._add_line_on_form(note, 200_000_000.0)
        self.assertEqual(note.amount, 500_000_000.0)

    def test_xoa_dong_cuoi_tren_form_ve_0(self):
        # Ô chỉ đọc nên không còn cách gõ lại: xoá hết dòng phải về 0.
        note = self._note(0.0)
        self._add_line_on_form(note, 300_000_000.0)
        with Form(note.with_user(self.user)) as form:
            form.disbursement_ids.remove(index=0)
        self.assertFalse(note.disbursement_ids)
        self.assertEqual(note.amount, 0.0)

    def test_so_nhap_tay_cu_khi_nhap_di_theo_dong(self):
        note = self._note(500_000_000.0)
        self._add_line_on_form(note, 100_000_000.0)
        self.assertEqual(note.amount, 100_000_000.0)

    # ----- Khế ước đã kích hoạt ---------------------------------------------
    def test_da_kich_hoat_so_tien_khop_dong_thi_di_theo(self):
        note = self._note(300_000_000.0)
        self._line(note, 300_000_000.0)
        note.action_activate()
        self._add_line_on_form(note, 100_000_000.0)
        self.assertEqual(note.amount, 400_000_000.0)

    def test_da_kich_hoat_so_tien_ky_khong_tut_theo_dong(self):
        # Khế ước cũ khai 500tr, chưa nhập dòng nào, nay nhập đợt đầu 100tr.
        note = self._note(500_000_000.0)
        note.action_activate()
        self._add_line_on_form(note, 100_000_000.0)
        self.assertEqual(note.amount, 500_000_000.0)
        self.assertEqual(note.principal_outstanding, 500_000_000.0)

    def test_so_tien_tu_phu_luc_khong_bi_ghi_de(self):
        note = self._note(300_000_000.0)
        self._line(note, 300_000_000.0)
        note.action_activate()
        note.amount = 800_000_000.0     # phụ lục đổi số tiền ghi thẳng như này
        self._add_line_on_form(note, 100_000_000.0)
        self.assertEqual(note.amount, 800_000_000.0)

    def test_huy_dot_khong_tut_so_tien_ky(self):
        note = self._note(500_000_000.0)
        self._line(note, 300_000_000.0)
        note.action_activate()
        extra = self._line(note, 100_000_000.0)
        self.assertIs(extra.action_cancel(), True)
        self.assertEqual(note.amount, 500_000_000.0)
        self.assertEqual(note.amount_disbursed, 300_000_000.0)

    # ----- Bấm nút khi chưa có dòng giải ngân -------------------------------
    def test_gui_nh_chua_co_dong_thi_bao(self):
        note = self._note(500_000_000.0)
        with self.assertRaises(UserError) as caught:
            self._button(note).action_send_to_bank()
        self.assertIn(note.name, str(caught.exception))
        self.assertEqual(note.state, 'draft')

    def test_kich_hoat_chua_co_dong_thi_bao(self):
        note = self._note(500_000_000.0)
        note.action_send_to_bank()
        with self.assertRaises(UserError):
            self._button(note).action_activate()
        self.assertEqual(note.state, 'sent_to_bank')

    def test_toan_dong_da_huy_coi_nhu_chua_co(self):
        note = self._note(100_000_000.0)
        self._line(note, 100_000_000.0).action_cancel()
        note.amount = 100_000_000.0
        with self.assertRaises(UserError):
            self._button(note).action_send_to_bank()

    def test_co_dong_thi_qua(self):
        note = self._note(100_000_000.0)
        self._line(note, 100_000_000.0)
        self._button(note).action_send_to_bank()
        self.assertEqual(note.state, 'sent_to_bank')
        self._button(note).action_activate()
        self.assertEqual(note.state, 'active')

    def test_luong_goi_bang_ma_khong_bi_chan(self):
        note = self._note(100_000_000.0)
        note.action_send_to_bank()
        note.action_activate()
        self.assertEqual(note.state, 'active')

    def test_hai_nut_tren_form_mang_co_kiem_tra(self):
        arch = self.env.ref('re_loan.view_re_loan_note_form').arch
        for name in ('action_send_to_bank', 'action_activate'):
            start = arch.index('name="%s"' % name)
            self.assertIn('check_disbursement_lines',
                          arch[start:arch.index('/>', start)], name)

    # ----- Cho vay lại vẫn nhập tay -----------------------------------------
    def _onlending(self):
        source = self._note(500_000_000.0)
        source.action_activate()
        child = self.env['res.partner'].create({
            'name': 'Công ty con 1594', 'is_company': True})
        return self.env['re.loan.note'].create({
            'name': 'KW-OL-1594', 'loan_type': 'onlending',
            'source_note_id': source.id, 'counterparty_id': child.id,
            'amount': 200_000_000.0, 'date_note': '2026-01-05',
            'tenor_months': 12, 'interest_rate': 11.0})

    def test_cho_vay_lai_khong_doi_hoi_dong_giai_ngan(self):
        note = self._onlending()
        self._button(note).action_send_to_bank()
        self.assertEqual(note.state, 'sent_to_bank')

    def test_cho_vay_lai_huy_dong_khong_doi_so_tien(self):
        note = self._onlending()
        line = self._line(note, 100_000_000.0)
        self.assertIs(line.action_cancel(), True)
        self.assertEqual(note.amount, 200_000_000.0)
