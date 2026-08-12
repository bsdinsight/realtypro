# -*- coding: utf-8 -*-
"""Cầu nối giao dịch ngân hàng ↔ IPC — đóng vòng "IPC ký rồi, tiền về chưa".

Sổ đệm `re.bank.transaction` (re_bank_sync, _common) KHÔNG biết IPC là gì.
Bridge này (ở _project) dạy nó:
- IPC là một đích đối soát hợp lệ (`_selection_matched_ref`).
- Tự khớp: tiền VÀO, `code`/nội dung chứa số IPC → gắn vào IPC đó.

IPC nhận thêm `amount_received` (Σ giao dịch đã khớp) — trả lời câu module
đang hở: IPC đã ký nhận rồi thì CĐT trả được bao nhiêu.
"""
import re

from odoo import _, api, fields, models


class ReBankTransactionIpc(models.Model):
    _inherit = 're.bank.transaction'

    ipc_id = fields.Many2one(
        'rp.owner.ipc', string='IPC đã khớp', index=True, copy=False)

    @api.model
    def _selection_matched_ref(self):
        sel = super()._selection_matched_ref()
        sel.append(('rp.owner.ipc', 'IPC — Chứng nhận thanh toán'))
        return sel

    def _try_auto_match(self):
        super()._try_auto_match()
        for txn in self:
            if txn.state != 'new' or txn.direction != 'in':
                continue
            ipc = txn._find_ipc()
            if ipc:
                txn.ipc_id = ipc.id
                txn.matched_ref = 'rp.owner.ipc,%s' % ipc.id
                txn.matched_note = _('Khớp IPC "%s" trong nội dung CK') % ipc.name
                txn.state = 'reconciled'
                ipc.message_post(body=_(
                    'Nhận <b>%(amt)s</b> từ CĐT qua ngân hàng '
                    '(%(bank)s, GD %(ref)s) — đã đối soát vào IPC.',
                    amt='{:,.0f}'.format(txn.amount),
                    bank=txn.bank_gateway or '', ref=txn.reference_code or ''))

    @staticmethod
    def _norm_code(s):
        """Bỏ mọi ký tự không phải chữ/số + viết hoa. IPC/2026/0006 →
        IPC20260006 — khớp được dù nội dung CK dùng / _ - hay khoảng trắng."""
        return re.sub(r'[^A-Z0-9]', '', (s or '').upper())

    def _find_ipc(self):
        """Tìm IPC mà TÊN (chuẩn hoá) xuất hiện trong code/nội dung CK.

        Format-agnostic: mã IPC có thể là IPC/2026/0006, IPC_0006, IPC0006 —
        chuẩn hoá cả 2 vế rồi so chuỗi con. Không phụ thuộc dạng mã cố định.
        """
        self.ensure_one()
        blob = self._norm_code('%s %s' % (self.code or '', self.content or ''))
        if not blob:
            return False
        for ipc in self.env['rp.owner.ipc'].search(
                [('state', '!=', 'cancelled')]):
            n = self._norm_code(ipc.name)
            if n and n in blob:
                return ipc
        return False


class RpOwnerIpcReceived(models.Model):
    _inherit = 'rp.owner.ipc'

    bank_txn_ids = fields.One2many(
        're.bank.transaction', 'ipc_id', string='Giao dịch NH đã khớp')
    amount_received = fields.Monetary(
        string='CĐT đã thu (thực nhận)', compute='_compute_amount_received',
        store=True, help='Σ giao dịch ngân hàng tiền vào đã đối soát vào IPC.')
    amount_receivable_open = fields.Monetary(
        string='Còn phải thu', compute='_compute_amount_received', store=True,
        help='Đề nghị CĐT thanh toán − đã thu.')

    @api.depends('bank_txn_ids.amount', 'bank_txn_ids.state', 'amount_net')
    def _compute_amount_received(self):
        for ipc in self:
            got = sum(t.amount for t in ipc.bank_txn_ids
                      if t.state == 'reconciled' and t.direction == 'in')
            ipc.amount_received = got
            ipc.amount_receivable_open = (ipc.amount_net or 0.0) - got
