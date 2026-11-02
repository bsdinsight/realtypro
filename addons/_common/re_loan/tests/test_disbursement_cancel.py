# -*- coding: utf-8 -*-
"""Việc 1595 — huỷ dòng giải ngân thì Số tiền KW tự tính lại và báo trên màn hình.

Số tiền KW = Σ các dòng chưa huỷ. Trước đây huỷ dòng thì số tiền đứng yên, khế
ước vẫn mang nguyên phần tiền của dòng đã bỏ.
"""
import html

from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tools.misc import formatLang


@tagged('post_install', '-at_install', 're_loan')
class TestDisbursementCancel(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bank = cls.env['res.partner'].create({
            'name': 'NH 1595', 'is_company': True, 'is_bank': True})
        cls.contract = cls.env['re.loan.credit.contract'].create({
            'name': 'HĐTD-1595', 'partner_id': cls.bank.id,
            'amount_total': 10_000_000_000.0})
        cls.contract.action_activate()
        cls.fac = cls.env['re.loan.facility'].create({
            'name': 'F-1595', 'credit_contract_id': cls.contract.id,
            'facility_type': 'revolving', 'amount_limit': 1_000_000_000.0,
            'interest_rate_default': 10.0})

    def _note(self, *amounts, name='KW-1595'):
        note = self.env['re.loan.note'].create({
            'name': name, 'facility_id': self.fac.id,
            'amount': sum(amounts), 'date_note': '2026-01-01',
            'tenor_months': 12, 'interest_rate': 10.0,
            'interest_method': 'declining', 'repayment_plan': 'bullet'})
        lines = self.env['re.loan.note.disbursement']
        for amount in amounts:
            lines |= self._line(note, amount)
        return note, lines

    def _line(self, note, amount):
        return self.env['re.loan.note.disbursement'].create({
            'note_id': note.id, 'date': '2026-01-05', 'amount': amount})

    def _fmt(self, note, value):
        return formatLang(self.env, value, currency_obj=note.currency_id)

    # ----- Khế ước còn Nháp -------------------------------------------------
    def test_huy_mot_dong_giam_so_tien_va_bao_tu_sang(self):
        note, lines = self._note(300_000_000.0, 200_000_000.0)
        result = lines[1].action_cancel()
        self.assertEqual(lines[1].state, 'cancelled')
        self.assertEqual(note.amount, 300_000_000.0)
        self.assertEqual(result['tag'], 'display_notification')
        message = result['params']['message']
        self.assertIn(self._fmt(note, 500_000_000.0), message)
        self.assertIn(self._fmt(note, 300_000_000.0), message)
        self.assertEqual(result['params']['next']['tag'], 'soft_reload',
                         'form khế ước phía sau phải đọc lại ô số tiền')
        self.assertIn(self._fmt(note, 300_000_000.0),
                      html.unescape(str(note.message_ids[0].body)),
                      'phải để lại vết')

    def test_huy_dong_cuoi_khi_nhap_ve_0(self):
        # Đúng ảnh của task: khế ước Nháp có một dòng, huỷ dòng đó.
        note, line = self._note(64_900.0)
        line.action_cancel()
        self.assertEqual(note.amount, 0.0)
        self.assertEqual(note.state, 'draft')

    def test_so_tien_da_khop_thi_khong_bao(self):
        note, lines = self._note(300_000_000.0, 200_000_000.0)
        note.amount = 300_000_000.0
        n_messages = len(note.message_ids)
        self.assertIs(lines[1].action_cancel(), True)
        self.assertEqual(len(note.message_ids), n_messages)

    def test_sua_dong_sau_khi_huy_khong_cong_lai_dong_da_huy(self):
        note, lines = self._note(300_000_000.0, 200_000_000.0)
        lines[1].action_cancel()
        note._onchange_disbursement_sum_amount()
        self.assertEqual(note.amount, 300_000_000.0)

    # ----- Đưa dòng đã huỷ về Nháp ------------------------------------------
    def test_ve_nhap_tang_lai_so_tien(self):
        note, lines = self._note(300_000_000.0, 200_000_000.0)
        lines[1].action_cancel()
        result = lines[1].action_reset_draft()
        self.assertEqual(lines[1].state, 'draft')
        self.assertEqual(note.amount, 500_000_000.0)
        self.assertEqual(result['tag'], 'display_notification')

    def test_ve_nhap_van_bi_chan_boi_han_muc(self):
        note, lines = self._note(500_000_000.0, 200_000_000.0)
        lines[1].action_cancel()
        other, _lines = self._note(500_000_000.0, name='KW-1595-B')
        other.action_activate()
        with self.assertRaises(ValidationError):
            lines[1].action_reset_draft()
        self.assertEqual(lines[1].state, 'cancelled')
        self.assertEqual(note.amount, 500_000_000.0)

    def test_dong_chua_huy_ve_nhap_khong_bao(self):
        note, line = self._note(100_000_000.0)
        note.action_send_to_bank()
        self.assertEqual(line.state, 'submitted')
        self.assertIs(line.action_reset_draft(), True)
        self.assertEqual(line.state, 'draft')

    # ----- Khế ước đã gửi ngân hàng -----------------------------------------
    def test_da_gui_nh_huy_mot_dong_van_giam(self):
        note, lines = self._note(300_000_000.0, 200_000_000.0)
        note.action_send_to_bank()
        lines[1].action_cancel()
        self.assertEqual(note.amount, 300_000_000.0)
        self.assertEqual(note.state, 'sent_to_bank')

    def test_da_gui_nh_khong_huy_duoc_dong_cuoi(self):
        note, line = self._note(100_000_000.0)
        note.action_send_to_bank()
        with self.assertRaises(UserError):
            line.action_cancel()
        self.assertEqual(line.state, 'submitted')
        self.assertEqual(note.amount, 100_000_000.0)

    # ----- Khế ước đã kích hoạt ---------------------------------------------
    def _active_note_with_extra_line(self):
        note, lines = self._note(300_000_000.0, 200_000_000.0)
        note.action_activate()
        note.amount = 600_000_000.0
        extra = self._line(note, 100_000_000.0)
        note.action_generate_interest_schedule()
        return note, extra

    def test_da_kich_hoat_huy_dong_them_sau_dung_lai_lich_lai(self):
        note, extra = self._active_note_with_extra_line()
        first = note.interest_line_ids.sorted('period_no')[0]
        self.assertEqual(first.principal_base, 600_000_000.0)
        extra.action_cancel()
        self.assertEqual(note.amount, 500_000_000.0)
        first = note.interest_line_ids.sorted('period_no')[0]
        self.assertEqual(first.principal_base, 500_000_000.0,
                         'lịch lãi phải theo số tiền mới')

    def test_da_giai_ngan_khong_cong_dong_da_huy(self):
        note, extra = self._active_note_with_extra_line()
        self.assertEqual(note.amount_disbursed, 600_000_000.0)
        extra.action_cancel()
        self.assertEqual(note.amount_disbursed, 500_000_000.0)

    def test_khong_giam_duoi_so_goc_da_tra(self):
        note, extra = self._active_note_with_extra_line()
        self.env['re.loan.note.repayment'].create({
            'note_id': note.id, 'date': '2026-02-01',
            'amount_principal': 550_000_000.0})
        with self.assertRaises(UserError):
            extra.action_cancel()
        self.assertEqual(extra.state, 'draft')
        self.assertEqual(note.amount, 600_000_000.0)

    def test_dong_da_chuyen_tien_van_khong_huy_duoc(self):
        note, lines = self._note(300_000_000.0, 200_000_000.0)
        note.action_activate()
        with self.assertRaises(UserError):
            lines[1].action_cancel()
        self.assertEqual(note.amount, 500_000_000.0)

    # ----- Huỷ cả khế ước ---------------------------------------------------
    def test_huy_khe_uoc_giu_nguyen_so_tien(self):
        # Huỷ khế ước kéo theo huỷ các dòng nhưng không đi qua nút Huỷ dòng:
        # số tiền giữ lại để còn biết khế ước đã huỷ từng là bao nhiêu.
        note, lines = self._note(300_000_000.0, 200_000_000.0)
        note.action_cancel()
        self.assertEqual(set(lines.mapped('state')), {'cancelled'})
        self.assertEqual(note.amount, 500_000_000.0)
