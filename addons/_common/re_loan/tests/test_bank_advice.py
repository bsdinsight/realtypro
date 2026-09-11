# -*- coding: utf-8 -*-
"""Giấy báo nợ (trích thu tự động) — phân bổ dư & net-off hai chiều.

Backlog 988: ngân hàng trích NHIỀU HƠN số các kỳ cần thì phần thừa
phải xử được — net-off nếu lẻ, phân bổ tiếp sang kỳ khác nếu lớn.
Trước đó chỉ chiều "NH trích thiếu" mới có đường ra.
"""
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 're_loan')
class TestBankAdvice(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bank = cls.env['res.partner'].create({
            'name': 'NH Advice', 'is_company': True, 'is_bank': True})
        cls.contract = cls.env['re.loan.credit.contract'].create({
            'name': 'HĐTD-ADV', 'partner_id': cls.bank.id,
            'amount_total': 10_000_000_000.0})
        cls.contract.action_activate()
        cls.fac = cls.env['re.loan.facility'].create({
            'name': 'F-adv', 'credit_contract_id': cls.contract.id,
            'facility_type': 'revolving', 'amount_limit': 10_000_000_000.0,
            'interest_rate_default': 10.0})
        cls.note = cls.env['re.loan.note'].create({
            'name': 'KW-ADV', 'facility_id': cls.fac.id,
            'amount': 1_000_000_000.0, 'date_note': '2026-01-01',
            'tenor_months': 12, 'interest_rate': 10.0,
            'interest_method': 'declining', 'repayment_plan': 'bullet'})
        cls.note.action_activate()
        # Phải có giải ngân thật: ràng buộc chặn trả gốc vượt số đã
        # giải ngân, mà bài kiểm này trả hết cả gốc lẫn lãi.
        cls.env['re.loan.note.disbursement'].create({
            'note_id': cls.note.id, 'date': '2026-01-05',
            'amount': 1_000_000_000.0, 'state': 'disbursed'})
        cls.threshold = cls.env['res.config.settings'].sudo(
        ).get_net_off_threshold()

    def _total_due(self):
        return sum(
            (l.principal_due or 0.0) + (l.interest_amount or 0.0)
            + (l.fee_amount or 0.0)
            for l in self.note.interest_line_ids)

    def _advice(self, amount, interest_line=None):
        adv = self.env['re.loan.bank.advice'].create({
            'date_advice': '2027-01-02',
            'partner_id': self.bank.id,
            'line_ids': [(0, 0, {
                'note_id': self.note.id,
                'amount': amount,
                'interest_line_id': interest_line and interest_line.id,
            })],
        })
        return adv

    # ----- NH trích DƯ, phần thừa lớn ------------------------------------
    def test_over_collection_marks_allocation_state(self):
        excess = self.threshold * 5
        adv = self._advice(self._total_due() + excess)
        self.assertEqual(adv.allocation_state, 'pending',
                         'chưa đăng thì chưa nói được gì về phân bổ')
        adv.action_post()
        line = adv.line_ids
        self.assertAlmostEqual(line.amount_unallocated, excess, delta=1)
        self.assertEqual(adv.allocation_state, 'over')
        self.assertEqual(adv.state, 'posted',
                         'trục phân bổ ĐỘC LẬP với trục chứng từ')

    def test_allocate_remainder_creates_draft_and_clears_parent(self):
        excess = self.threshold * 5
        adv = self._advice(self._total_due() + excess)
        adv.action_post()
        parent_line = adv.line_ids

        act = adv.action_allocate_remainder()
        new = self.env['re.loan.bank.advice'].browse(act['res_id'])
        self.assertEqual(new.state, 'draft')
        self.assertTrue(new.is_reallocation)
        self.assertEqual(new.name and new.name != adv.name, True,
                         'phiếu mới có số riêng')
        self.assertEqual(len(new.line_ids), 1)
        child = new.line_ids
        self.assertFalse(child.interest_line_id,
                         'KHÔNG chép kỳ chỉ định — để tự tìm kỳ khác')
        self.assertAlmostEqual(child.amount, excess, delta=1)
        self.assertEqual(child.source_line_id, parent_line)
        # Phần đã chuyển đi phải rời khỏi "Chưa allocate" của phiếu gốc,
        # không thì nút không bao giờ tắt và tiền bị đếm hai lần.
        parent_line.invalidate_recordset()
        adv.invalidate_recordset()
        self.assertAlmostEqual(parent_line.amount_unallocated, 0.0, delta=1)
        self.assertAlmostEqual(parent_line.amount_carried_forward, excess,
                               delta=1)
        self.assertEqual(adv.allocation_state, 'done')

    def test_cancel_child_returns_money_to_parent(self):
        excess = self.threshold * 5
        adv = self._advice(self._total_due() + excess)
        adv.action_post()
        new = self.env['re.loan.bank.advice'].browse(
            adv.action_allocate_remainder()['res_id'])
        new.action_cancel()
        adv.invalidate_recordset()
        adv.line_ids.invalidate_recordset()
        self.assertAlmostEqual(adv.line_ids.amount_unallocated, excess,
                               delta=1)
        self.assertEqual(adv.allocation_state, 'over',
                         'huỷ phiếu con thì tiền quay lại chỗ treo')

    def test_carry_cannot_exceed_source_remainder(self):
        excess = self.threshold * 5
        adv = self._advice(self._total_due() + excess)
        adv.action_post()
        new = self.env['re.loan.bank.advice'].browse(
            adv.action_allocate_remainder()['res_id'])
        with self.assertRaises(ValidationError):
            new.line_ids.amount = excess * 2

    def test_no_remainder_nothing_to_allocate(self):
        adv = self._advice(self._total_due())
        adv.action_post()
        self.assertEqual(adv.allocation_state, 'done')
        with self.assertRaises(UserError):
            adv.action_allocate_remainder()

    # ----- NH trích DƯ, phần thừa lẻ -> net-off ---------------------------
    def test_small_over_collection_is_net_off_able(self):
        excess = self.threshold / 2
        adv = self._advice(self._total_due() + excess)
        adv.action_post()
        line = adv.line_ids
        self.assertEqual(line.net_off_kind, 'over')
        self.assertTrue(line.net_off_allowed,
                        'lẻ trong ngưỡng thì net-off được, không phải '
                        'đẻ thêm phiếu')
        self.assertEqual(adv.allocation_state, 'done')
        line.action_auto_net_off()
        line.invalidate_recordset()
        self.assertAlmostEqual(line.amount_net_off, excess, delta=1)
        self.assertAlmostEqual(line.amount_unallocated, 0.0, delta=1)

    def test_over_beyond_threshold_refuses_net_off(self):
        adv = self._advice(self._total_due() + self.threshold * 5)
        adv.action_post()
        line = adv.line_ids
        self.assertEqual(line.net_off_kind, 'over')
        self.assertFalse(line.net_off_allowed)
        with self.assertRaises(UserError):
            line.action_auto_net_off()

    # ----- Chiều NH trích THIẾU vẫn như cũ --------------------------------
    def test_short_collection_still_nets_off_the_period(self):
        period = self.note.interest_line_ids.sorted('period_no')[0]
        due = ((period.principal_due or 0.0) + (period.interest_amount or 0.0)
               + (period.fee_amount or 0.0))
        short = min(self.threshold / 2, due / 2)
        adv = self._advice(due - short, interest_line=period)
        adv.action_post()
        line = adv.line_ids
        self.assertEqual(line.net_off_kind, 'short')
        self.assertTrue(line.net_off_allowed)
        line.action_auto_net_off()
        period.invalidate_recordset()
        self.assertEqual(period.state, 'paid')

    def test_net_off_blocked_before_post(self):
        adv = self._advice(self._total_due() + self.threshold / 2)
        with self.assertRaises(UserError):
            adv.line_ids.action_auto_net_off()

    # ----- Kỳ bị trích dư (backlog 988 vòng 3) ----------------------------
    def test_overpaid_period_is_flagged(self):
        """Kỳ ngân hàng trích DƯ phải hiện ra và được đánh dấu.

        Ba ô "còn lại" của kỳ đều kẹp sàn 0 nên trước đây kỳ trả dư
        đọc y hệt kỳ trả vừa đủ — không có chỗ nào nhìn ra.
        """
        period = self.note.interest_line_ids.sorted('period_no')[0]
        due = ((period.principal_due or 0.0)
               + (period.interest_amount or 0.0)
               + (period.fee_amount or 0.0))
        excess = 500_000.0
        adv = self._advice(due + excess, interest_line=period)
        adv.action_post()
        # Case A chặn đúng nghĩa vụ của kỳ: phần thừa nằm ở giấy báo
        period.invalidate_recordset()
        self.assertEqual(period.amount_overpaid, 0.0,
                         'giấy báo chỉ định kỳ thì không rót quá kỳ')
        self.assertAlmostEqual(adv.line_ids.amount_unallocated, excess,
                               delta=1)
        # Trả nợ nhập tay vượt nghĩa vụ -> kỳ trích dư
        self.env['re.loan.note.repayment'].create({
            'note_id': self.note.id, 'date': '2027-01-03',
            'interest_line_id': period.id,
            'amount_interest': excess})
        period.invalidate_recordset()
        self.assertAlmostEqual(period.amount_overpaid, excess, delta=1)
        self.assertTrue(period.has_net_off,
                        'kỳ trích dư phải được đánh dấu có net-off')
        self.assertEqual(period.amount_net_off, 0.0,
                         'nhưng KHÔNG cộng số trả dư vào "Tiền net-off" '
                         '— hai thứ ngược chiều nhau')

    def test_period_without_difference_is_not_flagged(self):
        period = self.note.interest_line_ids.sorted('period_no')[0]
        due = ((period.principal_due or 0.0)
               + (period.interest_amount or 0.0)
               + (period.fee_amount or 0.0))
        adv = self._advice(due, interest_line=period)
        adv.action_post()
        period.invalidate_recordset()
        self.assertEqual(period.amount_overpaid, 0.0)
        self.assertFalse(period.has_net_off)
