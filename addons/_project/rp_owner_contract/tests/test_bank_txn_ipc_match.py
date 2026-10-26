# -*- coding: utf-8 -*-
"""Tự khớp giao dịch ngân hàng → IPC chỉ đối soát khi CHẮC.

Lỗi được vá: khớp bằng chuỗi con + lấy IPC đầu tiên + không xét số tiền,
nhảy thẳng 'reconciled'. Tên không đệm số 0 thì IPC_1 khớp nhầm trong
IPC_12; tiền vượt đề nghị thanh toán vẫn ghi đã thu và kéo giá trị TSBĐ.
"""
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'rp_owner_contract')
class TestBankTxnIpcMatch(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        project = cls.env['re.project'].create(
            {'name': 'BankMatch-Test', 'code': 'BMT'})
        owner = cls.env['res.partner'].create(
            {'name': 'CĐT-BankMatch', 'is_company': True})
        cls.contract = cls.env['rp.owner.contract'].create({
            'name': 'HĐ-CĐT-BankMatch', 'project_id': project.id,
            'owner_id': owner.id,
            'contract_value_pretax': 100_000_000_000.0})
        cls.ipc_1 = cls._ipc('IPC_1', 10_000_000_000.0)
        cls.ipc_12 = cls._ipc('IPC_12', 20_000_000_000.0)

    @classmethod
    def _ipc(cls, name, gross):
        acc = cls.env['rp.owner.acceptance'].create({
            'contract_id': cls.contract.id, 'amount_this_period': gross})
        acc.action_propose()
        acc.action_approve()
        ipc = cls.env['rp.owner.ipc'].create({
            'name': name, 'contract_id': cls.contract.id,
            'acceptance_ids': [(6, 0, acc.ids)]})
        ipc.action_submit()
        return ipc

    def _ingest(self, content, amount, ext):
        txn, created = self.env['re.bank.transaction'].ingest({
            'source': 'manual', 'direction': 'in', 'amount': amount,
            'content': content, 'external_id': ext})
        self.assertTrue(created)
        return txn

    # ------------------------------------------------------------------
    def test_ipc_1_khong_khop_trong_ipc_12(self):
        self.assertGreater(self.ipc_12.amount_receivable_open, 1_000_000.0)
        txn = self._ingest('CDT TT IPC_12 dot 1', 1_000_000.0, 'm-12')
        self.assertEqual(txn.state, 'reconciled')
        self.assertEqual(txn.ipc_id, self.ipc_12,
                         'IPC_12 trong nội dung phải khớp IPC_12, không '
                         'phải IPC_1')
        self.assertEqual(self.ipc_1.amount_received, 0.0)

        txn1 = self._ingest('CDT TT IPC_1 dot 1', 1_000_000.0, 'm-1')
        self.assertEqual(txn1.state, 'reconciled')
        self.assertEqual(txn1.ipc_id, self.ipc_1)

    def test_nhieu_ipc_trong_noi_dung_cho_xac_nhan(self):
        txn = self._ingest('TT IPC_1 va IPC_12', 1_000_000.0, 'm-both')
        self.assertEqual(txn.state, 'matched',
                         'Nhiều IPC trùng mã thì không được tự đối soát')
        self.assertFalse(txn.ipc_id)
        self.assertEqual(self.ipc_1.amount_received, 0.0)
        self.assertEqual(self.ipc_12.amount_received, 0.0)
        with self.assertRaises(UserError):
            txn.action_confirm_ipc_match()

    def test_so_tien_vuot_con_phai_thu_cho_xac_nhan(self):
        open_amt = self.ipc_1.amount_receivable_open
        self.assertGreater(open_amt, 0.0)
        txn = self._ingest('TT IPC_1', open_amt + 1_000.0, 'm-over')
        self.assertEqual(txn.state, 'matched',
                         'Tiền vượt còn phải thu thì chờ người xác nhận')
        self.assertEqual(txn.ipc_id, self.ipc_1,
                         'Vẫn gợi ý IPC để người đối soát chốt nhanh')
        self.assertEqual(self.ipc_1.amount_received, 0.0,
                         '"Đã khớp" chưa được tính là đã thu')

        txn.action_confirm_ipc_match()
        self.assertEqual(txn.state, 'reconciled')
        self.assertEqual(self.ipc_1.amount_received, open_amt + 1_000.0)

    def test_dung_bang_con_phai_thu_van_tu_doi_soat(self):
        open_amt = self.ipc_12.amount_receivable_open
        txn = self._ingest('TT IPC_12', open_amt, 'm-exact')
        self.assertEqual(txn.state, 'reconciled')
        self.assertEqual(self.ipc_12.amount_receivable_open, 0.0)

    def test_ma_dang_so_nam_van_khop_moi_kieu_viet(self):
        ipc = self._ipc('IPC/2026/0006', 5_000_000_000.0)
        for i, content in enumerate(('IPC20260006 CDT thanh toan',
                                     'ipc 2026 0006 dot 1',
                                     'FT26001.IPC-2026-0006.CDT')):
            txn = self._ingest(content, 1_000.0, 'm-fmt-%s' % i)
            self.assertEqual(txn.ipc_id, ipc, content)
            self.assertEqual(txn.state, 'reconciled', content)

    def test_khong_co_ma_thi_de_moi(self):
        txn = self._ingest('chuyen tien', 1_000.0, 'm-none')
        self.assertEqual(txn.state, 'new')
        self.assertFalse(txn.ipc_id)
