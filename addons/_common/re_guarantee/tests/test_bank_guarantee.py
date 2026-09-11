# -*- coding: utf-8 -*-
"""Tests cho module re_guarantee — chứng thư BL."""
from datetime import date, timedelta

from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install', 're_guarantee')
class TestBankGuarantee(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bank = cls.env['res.partner'].create({
            'name': 'NH BL Test', 'is_company': True, 'is_bank': True})
        cls.applicant = cls.env['res.partner'].create({
            'name': 'Tổng thầu Applicant', 'is_company': True})
        cls.beneficiary = cls.env['res.partner'].create({
            'name': 'CĐT Beneficiary', 'is_company': True})
        cls.contract = cls.env['re.loan.credit.contract'].create({
            'name': 'HĐTD-BL', 'partner_id': cls.bank.id,
            'amount_total': 30_000_000_000.0})
        cls.contract.action_activate()
        # Hạn mức bảo lãnh khai bằng MỤC ĐÍCH, không bằng Loại — loại
        # 'guarantee_line' đã ngưng dùng (backlog 755). Fixture dựng
        # theo đúng cách hiện hành.
        cls.facility = cls.env['re.loan.facility'].create({
            'name': 'F-BL', 'credit_contract_id': cls.contract.id,
            'facility_type': 'revolving',
            'purpose': 'bank_guarantee',
            'amount_limit': 30_000_000_000.0})

    def _bl(self, amount=10_000_000_000.0, type_='performance',
            issue=None, expiry=None):
        return self.env['re.bank.guarantee'].create({
            'guarantee_type': type_,
            'issuing_bank_partner_id': self.bank.id,
            'applicant_partner_id': self.applicant.id,
            'beneficiary_partner_id': self.beneficiary.id,
            'date_issue': issue or '2026-01-01',
            'date_expiry': expiry or '2026-12-31',
            'amount': amount,
            'guarantee_fee_rate': 1.5,
            'deposit_rate': 5.0,
            'facility_id': self.facility.id,
        })

    # ----- Sequence + dates -----
    def test_auto_sequence(self):
        bl = self._bl()
        self.assertNotEqual(bl.name, '/')
        self.assertIn('BL', bl.name)

    def test_expiry_must_be_after_issue(self):
        with self.assertRaises(ValidationError):
            self._bl(issue='2026-06-01', expiry='2026-01-01')

    def test_amount_must_be_positive(self):
        with self.assertRaises(ValidationError):
            self._bl(amount=0.0)

    # ----- Auto compute fees -----
    def test_fee_amount_compute(self):
        # 10 tỷ × 1.5%/năm × 365/365 = 150tr
        bl = self._bl(issue='2026-01-01', expiry='2026-12-31')
        # delta = 364 ngày → 10t × 1.5% × 364/365 ≈ 149.589.041
        self.assertAlmostEqual(
            bl.guarantee_fee_amount,
            10_000_000_000.0 * 0.015 * 364 / 365.0,
            delta=1)

    def test_deposit_amount_compute(self):
        bl = self._bl()
        self.assertEqual(bl.deposit_amount, 500_000_000.0)  # 10t × 5%

    # ----- Workflow -----
    def test_workflow_draft_to_released(self):
        bl = self._bl()
        self.assertEqual(bl.state, 'draft')
        bl.action_issue()
        self.assertEqual(bl.state, 'issued')
        bl.action_release()
        self.assertEqual(bl.state, 'released')
        self.assertTrue(bl.date_released)

    def test_cannot_release_draft(self):
        bl = self._bl()
        with self.assertRaises(UserError):
            bl.action_release()

    def test_forfeit_workflow(self):
        bl = self._bl()
        bl.action_issue()
        bl.forfeit_amount = 8_000_000_000.0
        bl.forfeit_reason = 'Nhà thầu vi phạm tiến độ'
        bl.action_forfeit()
        self.assertEqual(bl.state, 'forfeited')
        self.assertTrue(bl.date_forfeited)

    # ----- Facility integration -----
    def test_facility_outstanding_includes_issued(self):
        bl1 = self._bl(amount=10_000_000_000.0)
        bl1.action_issue()
        bl2 = self._bl(amount=5_000_000_000.0)
        bl2.action_issue()
        self.facility.invalidate_recordset(
            ['guarantee_total_outstanding', 'guarantee_count'])
        self.assertEqual(self.facility.guarantee_count, 2)
        self.assertEqual(self.facility.guarantee_total_outstanding,
                         15_000_000_000.0)

    def test_facility_outstanding_excludes_released(self):
        bl1 = self._bl(amount=10_000_000_000.0)
        bl1.action_issue()
        bl1.action_release()
        self.facility.invalidate_recordset(['guarantee_total_outstanding'])
        self.assertEqual(self.facility.guarantee_total_outstanding, 0.0)

    # ----- Amendment: gia hạn -----
    def test_amendment_extension(self):
        bl = self._bl(expiry='2026-12-31')
        bl.action_issue()
        am = self.env['re.bank.guarantee.amendment'].create({
            'name': 'PL-EXT-01', 'guarantee_id': bl.id,
            'amendment_type': 'extension',
            'date_effective': '2026-12-01',
            'new_date_expiry': '2027-06-30'})
        am.action_apply()
        self.assertEqual(am.state, 'applied')
        self.assertEqual(str(bl.date_expiry), '2027-06-30')
        self.assertEqual(bl.state, 'extended')

    def test_amendment_amount_change(self):
        bl = self._bl(amount=10_000_000_000.0)
        bl.action_issue()
        am = self.env['re.bank.guarantee.amendment'].create({
            'name': 'PL-AMT-01', 'guarantee_id': bl.id,
            'amendment_type': 'amount',
            'date_effective': '2026-06-01',
            'new_amount': 15_000_000_000.0})
        am.action_apply()
        self.assertEqual(bl.amount, 15_000_000_000.0)

    # ----- Cron expiry -----
    def test_cron_auto_expire(self):
        # BL hết hạn 10 ngày trước hôm nay, vẫn issued
        bl = self._bl(
            issue=(date.today() - timedelta(days=370)).strftime('%Y-%m-%d'),
            expiry=(date.today() - timedelta(days=10)).strftime('%Y-%m-%d'),
        )
        bl.action_issue()
        self.env['re.bank.guarantee']._cron_check_expiry()
        self.assertEqual(bl.state, 'expired',
                         "BL quá hạn 10 ngày → auto expired")

    def test_cron_expiring_soon_creates_activity(self):
        # BL còn 15 ngày → tạo activity nhắc
        bl = self._bl(
            issue=(date.today() - timedelta(days=350)).strftime('%Y-%m-%d'),
            expiry=(date.today() + timedelta(days=15)).strftime('%Y-%m-%d'),
        )
        bl.action_issue()
        before = len(bl.activity_ids)
        self.env['re.bank.guarantee']._cron_check_expiry()
        bl.invalidate_recordset(['activity_ids'])
        after = len(bl.activity_ids)
        self.assertGreater(after, before,
                           "Cron phải tạo activity nhắc BL sắp hết hạn")

    # ----- Phiếu chi kế toán (backlog 969) --------------------------------
    def _configure_accounts(self):
        """Khai 4 TK + sổ nhật ký như khách hàng sẽ khai trên hệ thật."""
        Account = self.env['account.account']
        company = self.env.company

        def _acc(code, name, atype):
            acc = Account.search(
                [('code', '=', code), ('company_ids', 'in', company.id)],
                limit=1)
            return acc or Account.create({
                'code': code, 'name': name, 'account_type': atype})

        journal = self.env['account.journal'].search(
            [('type', '=', 'bank'), ('company_id', '=', company.id)],
            limit=1)
        if not journal:
            journal = self.env['account.journal'].create({
                'name': 'NH Test 969', 'type': 'bank', 'code': 'BNK969'})
        Param = self.env['ir.config_parameter'].sudo()
        accounts = {
            'fee': _acc('6425969', 'Phí BL', 'expense'),
            'penalty': _acc('811969', 'Phạt', 'expense'),
            'deposit': _acc('244969', 'Ký quỹ', 'asset_non_current'),
            'principal': _acc('3411969', 'Vay', 'liability_non_current'),
        }
        Param.set_param('re_guarantee.fee_account_id', accounts['fee'].id)
        Param.set_param('re_guarantee.penalty_account_id',
                        accounts['penalty'].id)
        Param.set_param('re_guarantee.deposit_account_id',
                        accounts['deposit'].id)
        Param.set_param('re_guarantee.principal_account_id',
                        accounts['principal'].id)
        Param.set_param('re_guarantee.payment_journal_id', journal.id)
        return accounts

    def _issued_bl(self):
        bl = self._bl()
        bl.facility_id = self.facility
        bl.action_issue()
        return bl

    def test_fee_payment_creates_outgoing_payment(self):
        accounts = self._configure_accounts()
        bl = self._issued_bl()
        pay = self.env['re.bank.guarantee.payment'].create({
            'guarantee_id': bl.id, 'payment_kind': 'fee',
            'date': '2026-02-01', 'amount': 3_000_000.0})
        self.assertTrue(pay.payment_id, 'đợt phí phải sinh phiếu chi')
        self.assertEqual(pay.payment_id.payment_type, 'outbound')
        debit = pay.payment_id.move_id.line_ids.filtered(lambda l: l.debit)
        self.assertEqual(debit.account_id, accounts['fee'],
                         'ghi Nợ đúng TK chi phí phí BL')

    def test_deposit_goes_to_asset_not_expense(self):
        accounts = self._configure_accounts()
        bl = self._issued_bl()
        pay = self.env['re.bank.guarantee.payment'].create({
            'guarantee_id': bl.id, 'payment_kind': 'deposit',
            'date': '2026-02-01', 'amount': 5_000_000.0})
        debit = pay.payment_id.move_id.line_ids.filtered(lambda l: l.debit)
        self.assertEqual(debit.account_id, accounts['deposit'])
        self.assertNotEqual(debit.account_id, accounts['fee'],
                            'ký quỹ KHÔNG phải chi phí')

    def test_deposit_refund_on_release(self):
        accounts = self._configure_accounts()
        bl = self._issued_bl()
        self.env['re.bank.guarantee.payment'].create({
            'guarantee_id': bl.id, 'payment_kind': 'deposit',
            'date': '2026-02-01', 'amount': 5_000_000.0})
        bl.invalidate_recordset()
        self.assertEqual(bl.deposit_paid_amount, 5_000_000.0)
        bl.action_release()
        bl.action_refund_deposit()
        bl.invalidate_recordset()
        refund = bl.deposit_refund_payment_id
        self.assertTrue(refund)
        self.assertEqual(refund.payment_type, 'inbound',
                         'NH trả lại tiền -> phiếu THU')
        credit = refund.move_id.line_ids.filtered(lambda l: l.credit)
        self.assertEqual(credit.account_id, accounts['deposit'],
                         'ghi Có TK ký quỹ -> tất toán số dư 244')
        with self.assertRaises(UserError):
            bl.action_refund_deposit()

    def test_payment_without_config_does_not_block(self):
        """Chưa khai TK thì vẫn ghi nhận được đợt thanh toán.

        Người nhập liệu đang ghi một giao dịch ĐÃ XẢY RA ở ngân hàng;
        chặn họ vì kế toán chưa khai tài khoản là mất luôn bản ghi.
        """
        Param = self.env['ir.config_parameter'].sudo()
        Param.set_param('re_guarantee.fee_account_id', False)
        bl = self._issued_bl()
        pay = self.env['re.bank.guarantee.payment'].create({
            'guarantee_id': bl.id, 'payment_kind': 'fee',
            'date': '2026-02-01', 'amount': 1_000_000.0})
        self.assertFalse(pay.payment_id)
        self.assertEqual(pay.amount, 1_000_000.0, 'bản ghi vẫn còn')
        with self.assertRaises(UserError):
            pay.action_create_payment()

    # ----- Đề nghị kích hoạt chiếm hạn mức (backlog 732 vòng 4) -----------
    def _bl_facility_with_room(self, room):
        """Hạn mức nhóm Bảo lãnh có khả dụng thực tế đúng bằng `room`.

        Dựng trên HĐTD RIÊNG: Σ hạn mức các mục đích không được vượt
        tổng HĐTD, mà HĐTD của fixture lớp đã dùng hết cho F-BL.

        Không cài re_loan_borrowing_base thì khả dụng thực tế rơi về
        "còn lại theo trần" — fixture đặt trần bằng room cho cả hai ca.
        """
        contract = self.env['re.loan.credit.contract'].create({
            'name': 'HĐTD-732-%s' % int(room), 'partner_id': self.bank.id,
            'amount_total': room})
        contract.action_activate()
        fac = self.env['re.loan.facility'].create({
            'name': 'F-BL-732', 'credit_contract_id': contract.id,
            'facility_type': 'revolving', 'purpose': 'bank_guarantee',
            'amount_limit': room})
        if 'borrowing_base_opening' in fac._fields:
            fac.borrowing_base_opening = room
        return fac

    def _request(self, facility, amount):
        return self.env['re.guarantee.request'].create({
            'guarantee_type': 'performance',
            'facility_id': facility.id,
            'issuing_bank_partner_id': self.bank.id,
            'applicant_partner_id': self.applicant.id,
            'beneficiary_partner_id': self.beneficiary.id,
            'date_expiry': '2027-12-31',
            'amount': amount,
        })

    def test_activated_request_consumes_limit(self):
        fac = self._bl_facility_with_room(10_000_000_000.0)
        req = self._request(fac, 4_000_000_000.0)
        fac.invalidate_recordset()
        self.assertEqual(fac.amount_used, 0.0, 'nháp chưa chiếm')
        req.action_activate()
        fac.invalidate_recordset()
        self.assertEqual(fac.amount_used, 4_000_000_000.0,
                         'kích hoạt là chiếm ngay')
        self.assertEqual(fac.amount_available, 6_000_000_000.0)

    def test_issue_does_not_double_count(self):
        fac = self._bl_facility_with_room(10_000_000_000.0)
        req = self._request(fac, 4_000_000_000.0)
        req.action_activate()
        req.action_issue()
        fac.invalidate_recordset()
        self.assertEqual(req.state, 'issued')
        self.assertEqual(fac.amount_used, 4_000_000_000.0,
                         'phát hành: chứng thư chiếm THAY đề nghị, '
                         'tổng không đổi')

    def test_full_room_request_can_still_issue(self):
        """Đề nghị chiếm TRỌN hạn mức vẫn phát hành được.

        Hồi quy cho lỗi đếm hai lần: từ lúc kích hoạt đề nghị đã nằm
        trong amount_used, nên nếu phép kiểm lúc phát hành không cộng
        ngược phần nó đang chiếm thì nó tự chặn chính mình.
        """
        fac = self._bl_facility_with_room(5_000_000_000.0)
        req = self._request(fac, 5_000_000_000.0)
        req.action_activate()
        fac.invalidate_recordset()
        self.assertEqual(fac.amount_available, 0.0)
        req.action_issue()
        self.assertEqual(req.state, 'issued')

    def test_second_request_blocked_after_first_activated(self):
        fac = self._bl_facility_with_room(5_000_000_000.0)
        self._request(fac, 3_000_000_000.0).action_activate()
        fac.invalidate_recordset()
        with self.assertRaises(ValidationError):
            self._request(fac, 3_000_000_000.0)

    def test_cancelled_request_releases_limit(self):
        fac = self._bl_facility_with_room(5_000_000_000.0)
        req = self._request(fac, 3_000_000_000.0)
        req.action_activate()
        fac.invalidate_recordset()
        self.assertEqual(fac.amount_used, 3_000_000_000.0)
        req.action_cancel()
        fac.invalidate_recordset()
        self.assertEqual(fac.amount_used, 0.0, 'huỷ là trả lại hạn mức')
