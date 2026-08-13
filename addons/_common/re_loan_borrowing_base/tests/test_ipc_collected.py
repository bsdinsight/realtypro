# -*- coding: utf-8 -*-
"""IPC đã thu tiền thì KHÔNG còn là tài sản bảo đảm nữa.

Lỗ hổng được vá: đối soát ngân hàng ghi tiền chủ đầu tư về từng IPC,
nhưng định giá tài sản bảo đảm cấp IPC vẫn lấy nguyên quyền đòi nợ.
Hệ quả là borrowing base tính trên khoản phải thu ĐÃ THU RỒI — hệ
thống báo còn dư địa vay trong khi tài sản bảo đảm đã tiêu biến. Sai
về phía nguy hiểm: cho rút vượt.
"""
from .common import BorrowingBaseCommon


class TestIpcCollected(BorrowingBaseCommon):

    def _signed_ipc(self, gross):
        """1 BBNT đã duyệt → 1 IPC đã được CĐT ký."""
        acc = self.env['rp.owner.acceptance'].create({
            'contract_id': self.owner_contract.id,
            'amount_this_period': gross})
        acc.action_propose()
        acc.action_approve()
        ipc = self.env['rp.owner.ipc'].create({
            'contract_id': self.owner_contract.id,
            'acceptance_ids': [(6, 0, acc.ids)]})
        ipc.action_submit()
        # ký nhận đòi đủ người ký + số văn bản — ngân hàng cần chứng từ
        # này khi nhận thế chấp quyền đòi nợ
        ipc.write({'signed_by_id': self.owner.id,
                   'sign_ref': 'CV-TEST/%s' % ipc.id})
        ipc.action_sign()
        return ipc

    def _collateral(self, ipc):
        """TSBĐ gắn ở CẤP IPC — giá trị do _sync_receivable_valuation đặt."""
        ctype = self.env['re.loan.collateral.type'].create({
            'name': 'Quyền đòi nợ', 'code': 'QDN-T', 'advance_rate': 0.6})
        col = self.env['re.loan.collateral'].create({
            'name': 'TSBĐ %s' % ipc.name, 'type_id': ctype.id,
            'owner_ipc_id': ipc.id})
        col._sync_receivable_valuation(reason='test')
        return col

    def _bank_in(self, ipc, amount):
        """Giao dịch tiền vào đã đối soát vào IPC."""
        txn, _new = self.env['re.bank.transaction'].ingest({
            'source': 'manual', 'direction': 'in', 'amount': amount,
            'content': 'TT %s' % ipc.name,
            'external_id': 'test-%s-%s' % (ipc.id, amount)})
        txn.write({'ipc_id': ipc.id, 'state': 'reconciled'})
        return txn

    # ------------------------------------------------------------------
    def test_gia_tri_tsbd_tru_phan_da_thu(self):
        ipc = self._signed_ipc(10_000_000_000.0)
        col = self._collateral(ipc)
        full = col.value_current
        self.assertGreater(full, 0.0, 'IPC ký rồi phải có giá trị TSBĐ')

        self._bank_in(ipc, 4_000_000_000.0)
        col.invalidate_recordset()
        self.assertAlmostEqual(
            col.value_current, full - 4_000_000_000.0, delta=1.0,
            msg='Thu 4 tỷ thì TSBĐ phải giảm đúng 4 tỷ')

    def test_thu_het_thi_tsbd_ve_khong_khong_am(self):
        ipc = self._signed_ipc(5_000_000_000.0)
        col = self._collateral(ipc)
        # trả dư hơn cả quyền đòi nợ — giá trị phải sàn ở 0, không âm
        self._bank_in(ipc, 9_000_000_000.0)
        col.invalidate_recordset()
        self.assertEqual(col.value_current, 0.0,
                         'Thu hết thì TSBĐ về 0 và không được âm')

    def test_go_doi_soat_thi_gia_tri_quay_lai(self):
        ipc = self._signed_ipc(8_000_000_000.0)
        col = self._collateral(ipc)
        full = col.value_current
        txn = self._bank_in(ipc, 3_000_000_000.0)
        col.invalidate_recordset()
        self.assertLess(col.value_current, full)

        # khớp nhầm → gỡ về "Mới nhận": TSBĐ phải hoàn nguyên
        txn.action_reset_new()
        col.invalidate_recordset()
        self.assertAlmostEqual(col.value_current, full, delta=1.0,
                               msg='Gỡ đối soát thì giá trị TSBĐ trở lại')
