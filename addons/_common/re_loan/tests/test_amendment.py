# -*- coding: utf-8 -*-
"""
Tests L2b — phụ lục khế ước (re.loan.note.amendment).
"""
from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 're_loan')
class TestAmendment(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bank = cls.env['res.partner'].create({
            'name': 'NH Amend', 'is_company': True, 'is_bank': True})
        cls.contract = cls.env['re.loan.credit.contract'].create({
            'name': 'HĐTD-AM', 'partner_id': cls.bank.id,
            'amount_total': 10_000_000_000.0})
        cls.contract.action_activate()
        cls.fac = cls.env['re.loan.facility'].create({
            'name': 'F-am', 'credit_contract_id': cls.contract.id,
            'facility_type': 'revolving', 'amount_limit': 10_000_000_000.0,
            'interest_rate_default': 10.0})
        cls.note = cls.env['re.loan.note'].create({
            'name': 'KW-AM', 'facility_id': cls.fac.id,
            'amount': 1_000_000_000.0, 'date_note': '2026-01-01',
            'tenor_months': 12, 'interest_rate': 10.0,
            'interest_method': 'declining', 'repayment_plan': 'bullet'})
        cls.note.action_activate()

    def _amend(self, atype, **vals):
        return self.env['re.loan.note.amendment'].create({
            'name': 'PL-%s' % atype, 'note_id': self.note.id,
            'amendment_type': atype, 'date_effective': '2026-06-01',
            **vals})

    # ----- Extension ------------------------------------------------------
    def test_extension_changes_maturity(self):
        old = self.note.date_maturity
        am = self._amend('extension', new_date_maturity='2027-06-01')
        am.action_apply()
        self.assertEqual(str(self.note.date_maturity), '2027-06-01')
        self.assertNotEqual(self.note.date_maturity, old)
        self.assertEqual(am.state, 'applied')

    # ----- Rate -----------------------------------------------------------
    def test_rate_change_only_future_periods(self):
        # KW gốc rate 10%. Phụ lục đổi rate 14% hiệu lực 2026-06-01.
        # Các kỳ date_from < 2026-06-01 phải giữ 10%, kỳ ≥ 2026-06-01
        # phải là 14%.
        am = self._amend('rate', new_interest_rate=14.0)
        # date_effective = 2026-06-01 (đã set ở _amend)
        am.action_apply()
        # interest_rate là rate KÝ BAN ĐẦU, IMMUTABLE.
        # Phụ lục KHÔNG overwrite field này.
        self.assertEqual(self.note.interest_rate, 10.0,
                         'Phụ lục KHÔNG được overwrite rate ký ban đầu')
        # Rate hiệu lực SAU ngày cutover 2026-06-01 lấy qua
        # _effective_rate_at — phải là rate phụ lục (14%).
        self.assertEqual(
            self.note._effective_rate_at(
                fields.Date.to_date('2026-08-01')), 14.0)
        # Rate hiệu lực TRƯỚC ngày cutover — vẫn là rate ký ban đầu (10%).
        self.assertEqual(
            self.note._effective_rate_at(
                fields.Date.to_date('2026-03-01')), 10.0)
        lines = self.note.interest_line_ids.sorted('period_no')
        past = lines.filtered(lambda l: l.date_from
                              and str(l.date_from) < '2026-06-01')
        future = lines.filtered(lambda l: l.date_from
                                and str(l.date_from) >= '2026-06-01')
        self.assertTrue(past, 'Phải có kỳ trước cutover')
        self.assertTrue(future, 'Phải có kỳ sau cutover')
        self.assertTrue(all(l.interest_rate == 10.0 for l in past),
                        'Kỳ trước cutover phải giữ rate cũ 10%')
        self.assertTrue(all(l.interest_rate == 14.0 for l in future),
                        'Kỳ sau cutover phải là rate mới 14%')

    def test_rate_change_regenerate_preserves_history(self):
        # Bug #3: sau khi áp phụ lục đổi rate, nếu user bấm "Tạo lại
        # lịch lãi", các kỳ TRƯỚC date_effective phải vẫn giữ rate cũ
        # (10%), không bị overwrite về rate mới (14%).
        am = self._amend('rate', new_interest_rate=14.0)
        am.action_apply()
        # User bấm Tạo lại lịch lãi (regenerate full schedule)
        self.note.action_generate_interest_schedule()
        lines = self.note.interest_line_ids.sorted('period_no')
        past = lines.filtered(lambda l: l.date_from
                              and str(l.date_from) < '2026-06-01')
        future = lines.filtered(lambda l: l.date_from
                                and str(l.date_from) >= '2026-06-01')
        self.assertTrue(all(l.interest_rate == 10.0 for l in past),
                        'Regenerate: kỳ trước phụ lục vẫn phải = 10%')
        self.assertTrue(all(l.interest_rate == 14.0 for l in future),
                        'Regenerate: kỳ sau phụ lục phải = 14%')

    def test_rate_change_two_amendments_cascade(self):
        # KW gốc 10%. Phụ lục 1: 14% hiệu lực 2026-06-01.
        # Phụ lục 2: 16% hiệu lực 2026-09-01.
        # Sau cả 2 + regenerate:
        #   kỳ trước 2026-06-01 → 10%
        #   kỳ 2026-06-01 ≤ < 2026-09-01 → 14%
        #   kỳ ≥ 2026-09-01 → 16%
        am1 = self._amend('rate', new_interest_rate=14.0)
        am1.action_apply()
        am2 = self.env['re.loan.note.amendment'].create({
            'name': 'PL2', 'note_id': self.note.id,
            'amendment_type': 'rate', 'new_interest_rate': 16.0,
            'date_effective': '2026-09-01'})
        am2.action_apply()
        self.note.action_generate_interest_schedule()
        for line in self.note.interest_line_ids:
            d = str(line.date_from)
            if d < '2026-06-01':
                self.assertEqual(line.interest_rate, 10.0,
                                 'Kỳ %s phải = 10%%' % d)
            elif d < '2026-09-01':
                self.assertEqual(line.interest_rate, 14.0,
                                 'Kỳ %s phải = 14%%' % d)
            else:
                self.assertEqual(line.interest_rate, 16.0,
                                 'Kỳ %s phải = 16%%' % d)

    # ----- Amount ---------------------------------------------------------
    def test_amount_change(self):
        am = self._amend('amount', new_amount=1_500_000_000.0)
        am.action_apply()
        self.assertEqual(self.note.amount, 1_500_000_000.0)

    def test_amount_must_be_positive(self):
        with self.assertRaises(ValidationError):
            self._amend('amount', new_amount=0.0)

    # ----- Purpose --------------------------------------------------------
    def test_purpose_change(self):
        am = self._amend('purpose', new_purpose='Mục đích mới ABC')
        am.action_apply()
        self.assertEqual(self.note.purpose, 'Mục đích mới ABC')

    # ----- Schedule -------------------------------------------------------
    def test_schedule_change_regenerates(self):
        am = self._amend('schedule', new_repayment_plan='equal_principal')
        am.action_apply()
        self.assertEqual(self.note.repayment_plan, 'equal_principal')
        # equal_principal declining → dư nợ giảm dần qua các kỳ
        lines = self.note.interest_line_ids.sorted('period_no')
        self.assertGreater(lines[0].principal_base, lines[11].principal_base)

    # ----- Audit + guards -------------------------------------------------
    def test_value_old_new_recorded(self):
        am = self._amend('rate', new_interest_rate=11.5)
        am.action_apply()
        self.assertEqual(am.value_old, '10.00')
        self.assertEqual(am.value_new, '11.50')

    def test_cannot_apply_twice(self):
        am = self._amend('rate', new_interest_rate=11.0)
        am.action_apply()
        with self.assertRaises(UserError):
            am.action_apply()

    def test_cannot_unlink_applied(self):
        am = self._amend('rate', new_interest_rate=11.0)
        am.action_apply()
        with self.assertRaises(UserError):
            am.unlink()

    def test_cannot_apply_on_draft_note(self):
        draft_note = self.env['re.loan.note'].create({
            'name': 'KW-draft', 'facility_id': self.fac.id,
            'amount': 100_000_000.0, 'date_note': '2026-01-01',
            'tenor_months': 6})
        am = self.env['re.loan.note.amendment'].create({
            'name': 'PL-x', 'note_id': draft_note.id,
            'amendment_type': 'rate', 'new_interest_rate': 9.0})
        with self.assertRaises(UserError):
            am.action_apply()

    # ----- Chênh lệch hồi tố (backlog 737) --------------------------------
    def _accrue_first_periods(self, n=2):
        """Đưa n kỳ lãi đầu về 'đã ghi nhận' — điều kiện để có hồi tố."""
        lines = self.note.interest_line_ids.sorted('period_no')[:n]
        lines.write({'state': 'accrued'})
        return lines

    def test_retroactive_flag_auto_on(self):
        """Cờ hồi tố tự bật khi ngày hiệu lực nằm trước kỳ đã ghi nhận."""
        lines = self._accrue_first_periods(2)
        eff = min(lines.mapped('date_to')) - timedelta(days=1)
        am = self._amend('rate', new_interest_rate=15.0, date_effective=eff)
        self.assertTrue(am.is_retroactive)
        # Ngày hiệu lực sau mọi kỳ đã ghi nhận -> không hồi tố
        later = max(self.note.interest_line_ids.mapped('date_to'))
        am2 = self.env['re.loan.note.amendment'].create({
            'name': 'PL-not-retro', 'note_id': self.note.id,
            'amendment_type': 'rate', 'new_interest_rate': 15.0,
            'date_effective': later})
        self.assertFalse(am2.is_retroactive)

    def test_delta_computed_on_save(self):
        """Lưu phụ lục hồi tố là có bảng Δ ngay — không phải bấm nút.

        Backlog 737: phụ lục được khai bằng hộp thoại dòng one2many
        trên khế ước. Bản ghi chưa lưu thì nút "Tính chênh lệch" chạy
        không nổi (thiếu note_id), nên bảng phải tự dựng lúc lưu.
        """
        lines = self._accrue_first_periods(2)
        eff = min(lines.mapped('date_to')) - timedelta(days=1)
        am = self._amend('rate', new_interest_rate=15.0, date_effective=eff)
        self.assertEqual(am.delta_state, 'computed')
        self.assertEqual(am.delta_count, 2)
        self.assertTrue(am.delta_total)

    def test_delta_recomputed_when_effective_date_moves(self):
        lines = self._accrue_first_periods(2)
        eff = max(lines.mapped('date_to')) - timedelta(days=1)
        am = self._amend('rate', new_interest_rate=15.0, date_effective=eff)
        self.assertEqual(am.delta_count, 1)
        am.date_effective = min(lines.mapped('date_to')) - timedelta(days=1)
        self.assertEqual(am.delta_count, 2, 'Δ phải tính lại theo ngày mới')

    def test_delta_not_touched_once_approved(self):
        lines = self._accrue_first_periods(2)
        eff = min(lines.mapped('date_to')) - timedelta(days=1)
        am = self._amend('rate', new_interest_rate=15.0, date_effective=eff)
        am.action_approve_delta()
        self.assertEqual(am.delta_state, 'approved')
        am.new_interest_rate = 16.0
        self.assertEqual(am.delta_state, 'approved',
                         'số đã duyệt không được tự ghi đè')
        with self.assertRaises(UserError):
            am.action_compute_delta()

    def test_non_rate_amendment_has_no_delta(self):
        self._accrue_first_periods(2)
        am = self._amend('extension', new_date_maturity='2027-06-01')
        self.assertFalse(am.is_retroactive)
        self.assertEqual(am.delta_state, 'none')
