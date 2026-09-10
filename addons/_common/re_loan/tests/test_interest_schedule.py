# -*- coding: utf-8 -*-
"""
Tests L2a — lịch lãi tự động (re.loan.note.interest.line) + thuật toán.
"""
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 're_loan')
class TestInterestSchedule(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bank = cls.env['res.partner'].create({
            'name': 'NH IntTest', 'is_company': True, 'is_bank': True})
        cls.contract = cls.env['re.loan.credit.contract'].create({
            'name': 'HĐTD-INT', 'partner_id': cls.bank.id,
            'amount_total': 10_000_000_000.0})
        cls.contract.action_activate()
        cls.fac = cls.env['re.loan.facility'].create({
            'name': 'F-int', 'credit_contract_id': cls.contract.id,
            'facility_type': 'revolving', 'amount_limit': 10_000_000_000.0,
            'interest_rate_default': 12.0})

    def _note(self, method='declining', plan='bullet', tenor=12,
              rate=12.0, amount=1_200_000_000.0, maturity=None):
        vals = {
            'name': 'KW-%s-%s-%s' % (method, plan, tenor),
            'facility_id': self.fac.id, 'amount': amount,
            'date_note': '2026-01-01', 'interest_rate': rate,
            'interest_method': method, 'repayment_plan': plan,
            'day_count': 'act_360',
        }
        if tenor:
            vals['tenor_months'] = tenor
        if maturity:
            vals['date_maturity'] = maturity
        return self.env['re.loan.note'].create(vals)

    # ----- Generation -----------------------------------------------------
    def test_schedule_generated_on_activate(self):
        note = self._note(tenor=12)
        note.action_activate()
        self.assertEqual(len(note.interest_line_ids), 12)
        self.assertTrue(all(l.state == 'planned'
                            for l in note.interest_line_ids))

    def test_bullet_declining_base_constant(self):
        note = self._note(method='declining', plan='bullet', tenor=12)
        note.action_activate()
        bases = note.interest_line_ids.mapped('principal_base')
        self.assertTrue(all(b == 1_200_000_000.0 for b in bases))

    def test_equal_principal_declining_base_decreases(self):
        note = self._note(method='declining', plan='equal_principal',
                          tenor=12)
        note.action_activate()
        lines = note.interest_line_ids.sorted('period_no')
        self.assertEqual(lines[0].principal_base, 1_200_000_000.0)
        # giảm 100tr mỗi kỳ
        self.assertEqual(lines[1].principal_base, 1_100_000_000.0)
        self.assertEqual(lines[11].principal_base, 100_000_000.0)

    def test_flat_base_constant_even_with_equal_principal(self):
        note = self._note(method='flat', plan='equal_principal', tenor=12)
        note.action_activate()
        bases = note.interest_line_ids.mapped('principal_base')
        self.assertTrue(all(b == 1_200_000_000.0 for b in bases))

    # ----- Formula --------------------------------------------------------
    def test_interest_formula_act360(self):
        note = self._note(method='declining', plan='bullet', tenor=12,
                          rate=12.0)
        note.action_activate()
        line1 = note.interest_line_ids.sorted('period_no')[0]
        # base 1.2e9 * 12% * days/360
        expected = 1_200_000_000.0 * 0.12 * line1.days / 360.0
        self.assertAlmostEqual(line1.interest_amount, expected, delta=1.0)

    def test_day_count_365_less_than_360(self):
        n360 = self._note(tenor=12)
        n360.action_activate()
        n365 = self._note(tenor=12)
        n365.day_count = 'act_365'
        n365.action_generate_interest_schedule()
        # /365 < /360 → tổng lãi act_365 nhỏ hơn
        self.assertLess(n365.interest_total_planned,
                        n360.interest_total_planned)

    def test_total_planned(self):
        note = self._note(tenor=12)
        note.action_activate()
        total = sum(note.interest_line_ids.mapped('interest_amount'))
        self.assertAlmostEqual(note.interest_total_planned, total, delta=1.0)

    # ----- Override -------------------------------------------------------
    def test_override_line(self):
        note = self._note(tenor=12)
        note.action_activate()
        line = note.interest_line_ids.sorted('period_no')[0]
        line.write({'is_overridden': True,
                    'interest_amount_manual': 99_000_000.0})
        self.assertEqual(line.interest_amount, 99_000_000.0)

    # ----- Single period (no tenor) --------------------------------------
    def test_single_period_when_no_tenor(self):
        note = self._note(tenor=0, maturity='2026-12-31')
        note.action_activate()
        self.assertEqual(len(note.interest_line_ids), 1)
        line = note.interest_line_ids
        self.assertEqual(str(line.date_from), '2026-01-01')
        self.assertEqual(str(line.date_to), '2026-12-31')

    # ----- Regenerate keeps non-planned ----------------------------------
    def test_regenerate_keeps_accrued(self):
        note = self._note(tenor=12)
        note.action_activate()
        first = note.interest_line_ids.sorted('period_no')[0]
        first.state = 'accrued'
        note.action_generate_interest_schedule()
        # Kỳ đã ghi nhận được GIỮ, và lịch mới KHÔNG sinh lại chính kỳ
        # đó nữa → vẫn đúng 12 dòng, không phải 13 (backlog 731).
        # Bản cũ trả 13 vì kỳ 1 bị nhân đôi — tổng phải trả gấp đôi.
        self.assertEqual(len(note.interest_line_ids), 12)
        periods = note.interest_line_ids.mapped('period_no')
        self.assertEqual(len(periods), len(set(periods)),
                         'không kỳ nào được sinh trùng')
        self.assertEqual(
            len(note.interest_line_ids.filtered(
                lambda l: l.state == 'accrued')), 1)

    # ----- Tiền gốc phải trả theo Kế hoạch trả gốc (#16) -----------------

    def test_principal_due_bullet(self):
        # Bullet: 12 kỳ × 100tr, kỳ 1..11 = 0, kỳ 12 = full 1.2 tỷ
        note = self._note(plan='bullet', tenor=12,
                          amount=1_200_000_000.0)
        note.action_generate_interest_schedule()
        lines = note.interest_line_ids.sorted('period_no')
        self.assertEqual(len(lines), 12)
        for line in lines[:-1]:
            self.assertEqual(line.principal_due, 0.0,
                             "Bullet: kỳ %s phải = 0" % line.period_no)
        self.assertEqual(lines[-1].principal_due, 1_200_000_000.0,
                         "Bullet: kỳ cuối phải = full amount")
        # Σ principal_due = amount
        self.assertEqual(sum(lines.mapped('principal_due')),
                         1_200_000_000.0)

    def test_principal_due_equal(self):
        # Equal: mỗi kỳ = 1.2 tỷ / 12 = 100tr
        note = self._note(plan='equal_principal', tenor=12,
                          amount=1_200_000_000.0)
        note.action_generate_interest_schedule()
        lines = note.interest_line_ids.sorted('period_no')
        for line in lines:
            self.assertEqual(line.principal_due, 100_000_000.0,
                             "Equal: kỳ %s phải = 100tr"
                             % line.period_no)
        self.assertEqual(sum(lines.mapped('principal_due')),
                         1_200_000_000.0)

    def test_principal_due_custom_default_zero(self):
        # Custom: principal_due mặc định = 0, user nhập tay
        note = self._note(plan='custom', tenor=12,
                          amount=1_200_000_000.0)
        note.action_generate_interest_schedule()
        lines = note.interest_line_ids.sorted('period_no')
        for line in lines:
            self.assertEqual(line.principal_due, 0.0,
                             "Custom: mặc định = 0, user nhập tay")
        # User nhập tay 2 kỳ
        lines[0].principal_due = 500_000_000.0
        lines[5].principal_due = 700_000_000.0
        self.assertEqual(sum(lines.mapped('principal_due')),
                         1_200_000_000.0)

    def test_total_due_equals_principal_plus_interest(self):
        note = self._note(plan='equal_principal', tenor=12,
                          amount=1_200_000_000.0, rate=12.0)
        note.action_generate_interest_schedule()
        for line in note.interest_line_ids:
            self.assertAlmostEqual(
                line.total_due,
                line.principal_due + line.interest_amount,
                places=2,
                msg="Tổng phải trả = gốc + lãi của cùng kỳ")

    def test_principal_due_switch_plan_recomputes(self):
        # Đổi plan từ bullet → equal_principal trên KW đã generate.
        # Lưu ý: principal_due recompute vì depends; principal_base
        # KHÔNG đổi cho đến khi user bấm "Tạo lại lịch lãi".
        note = self._note(plan='bullet', tenor=12,
                          amount=1_200_000_000.0)
        note.action_generate_interest_schedule()
        # Verify bullet
        self.assertEqual(note.interest_line_ids.sorted(
            'period_no')[0].principal_due, 0.0)
        # Switch plan
        note.repayment_plan = 'equal_principal'
        note.interest_line_ids.invalidate_recordset(['principal_due'])
        # Mỗi kỳ giờ phải = 100tr
        for line in note.interest_line_ids:
            self.assertEqual(line.principal_due, 100_000_000.0)

    # ----- Quick repayment từ dòng lịch lãi --------------------------

    def test_action_create_repayment_from_line(self):
        # KW 1.2 tỷ trả gốc đều 12 kỳ, 12% /năm
        note = self._note(plan='equal_principal', tenor=12,
                          amount=1_200_000_000.0, rate=12.0)
        note.action_generate_interest_schedule()
        # Phải giải ngân trước để repayment không bị chặn bởi
        # constraint repaid ≤ disbursed
        self.env['re.loan.note.disbursement'].create({
            'note_id': note.id, 'amount': 1_200_000_000.0,
            'date': '2026-01-01'})

        line = note.interest_line_ids.sorted('period_no')[0]
        before_count = len(note.repayment_ids)

        action = line.action_create_repayment()

        # Nút chỉ MỞ FORM, chưa tạo gì. Người dùng bấm Huỷ trên hộp
        # thoại thì không được để lại dòng trả nợ nào — trước đây nút
        # create() trước rồi mới mở form, nên bấm Huỷ vẫn ghi nhận đã
        # thanh toán (backlog 747).
        self.assertEqual(len(note.repayment_ids), before_count)
        self.assertNotEqual(line.state, 'paid')
        self.assertEqual(action['res_model'], 're.loan.note.repayment')
        self.assertFalse(action.get('res_id'))
        self.assertEqual(action['target'], 'new')

        # Số của kỳ được điền sẵn vào form
        ctx = action['context']
        self.assertEqual(ctx['default_interest_line_id'], line.id)
        self.assertEqual(ctx['default_amount_principal'],
                         line.principal_due)
        self.assertEqual(ctx['default_amount_interest'],
                         line.interest_amount)

        # Bấm Lưu (client create theo default_) mới ghi nhận
        self.env['re.loan.note.repayment'].with_context(**ctx).create({
            'note_id': note.id,
            'date': line.date_to,
            'amount_principal': ctx['default_amount_principal'],
            'amount_interest': ctx['default_amount_interest'],
            'interest_line_id': line.id,
        })
        self.assertEqual(len(note.repayment_ids), before_count + 1)
        self.assertEqual(line.state, 'paid')

    def _pay_period(self, line):
        """Mô phỏng người dùng bấm Thanh toán rồi Lưu."""
        ctx = line.action_create_repayment()['context']
        return self.env['re.loan.note.repayment'].with_context(
            **ctx).create({
                'note_id': line.note_id.id,
                'date': line.date_to,
                'amount_principal': ctx['default_amount_principal'],
                'amount_interest': ctx['default_amount_interest'],
                'interest_line_id': line.id,
            })

    def test_action_create_repayment_blocked_on_paid_line(self):
        from odoo.exceptions import UserError
        note = self._note(plan='equal_principal', tenor=12,
                          amount=1_200_000_000.0)
        note.action_generate_interest_schedule()
        self.env['re.loan.note.disbursement'].create({
            'note_id': note.id, 'amount': 1_200_000_000.0,
            'date': '2026-01-01'})
        line = note.interest_line_ids.sorted('period_no')[0]
        self._pay_period(line)
        self.assertEqual(line.state, 'paid')
        # Kỳ đã trả đủ → UserError "đã ghi nhận"
        with self.assertRaises(UserError):
            line.action_create_repayment()

    def test_regenerate_keeps_paid_period_once(self):
        """Tạo lại lịch lãi KHÔNG nhân đôi kỳ đã thanh toán (747/731)."""
        note = self._note(plan='equal_principal', tenor=12,
                          amount=1_200_000_000.0, rate=12.0)
        note.action_generate_interest_schedule()
        self.env['re.loan.note.disbursement'].create({
            'note_id': note.id, 'amount': 1_200_000_000.0,
            'date': '2026-01-01'})
        first = note.interest_line_ids.sorted('period_no')[0]
        self._pay_period(first)

        before = len(note.interest_line_ids)
        note.action_generate_interest_schedule()
        periods = note.interest_line_ids.filtered(
            lambda l: l.line_type == 'period').mapped('period_no')
        self.assertEqual(len(note.interest_line_ids), before,
                         'regen không được sinh thêm dòng')
        self.assertEqual(len(periods), len(set(periods)),
                         'không kỳ nào bị trùng')
        self.assertTrue(first.exists())
        self.assertEqual(first.state, 'paid',
                         'kỳ đã trả giữ nguyên trạng thái')
