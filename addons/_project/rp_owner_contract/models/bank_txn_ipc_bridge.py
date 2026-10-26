# -*- coding: utf-8 -*-
"""Cầu nối giao dịch ngân hàng ↔ IPC — đóng vòng "IPC ký rồi, tiền về chưa".

Sổ đệm `re.bank.transaction` (re_bank_sync, _common) KHÔNG biết IPC là gì.
Bridge này (ở _project) dạy nó:
- IPC là một đích đối soát hợp lệ (`_selection_matched_ref`).
- Tự khớp: tiền VÀO, `code`/nội dung chứa số IPC → gắn vào IPC đó; chỉ
  tự đối soát khi đúng 1 IPC và số tiền vừa, còn lại chờ người xác nhận.

IPC nhận thêm `amount_received` (Σ giao dịch đã khớp) — trả lời câu module
đang hở: IPC đã ký nhận rồi thì CĐT trả được bao nhiêu.
"""
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError


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
        """Tiền VÀO có mã IPC → khớp.

        Chỉ tự đối soát (`reconciled`) khi chắc: đúng MỘT IPC và số tiền
        không vượt còn phải thu. Còn lại để `matched` chờ người xác nhận —
        đối soát nhầm là IPC ghi đã thu + TSBĐ bị định giá lại sai.
        """
        super()._try_auto_match()
        for txn in self:
            if txn.state != 'new' or txn.direction != 'in':
                continue
            ipcs = txn._find_ipc_candidates()
            if not ipcs:
                continue
            if len(ipcs) > 1:
                txn.write({
                    'state': 'matched',
                    'matched_note': _(
                        'Nội dung CK chứa mã của nhiều IPC (%s) — chọn IPC '
                        'rồi xác nhận', ', '.join(ipcs.mapped('name'))),
                })
                continue
            vals = {'ipc_id': ipcs.id,
                    'matched_ref': 'rp.owner.ipc,%s' % ipcs.id}
            if txn._ipc_amount_fits(ipcs):
                vals.update(state='reconciled', matched_note=_(
                    'Khớp IPC "%s" trong nội dung CK') % ipcs.name)
                txn.write(vals)
                txn._post_ipc_received()
            else:
                vals.update(state='matched', matched_note=_(
                    'Khớp mã IPC "%(n)s" nhưng số tiền %(a)s vượt còn phải '
                    'thu %(o)s — chờ xác nhận',
                    n=ipcs.name, a='{:,.0f}'.format(txn.amount),
                    o='{:,.0f}'.format(ipcs.amount_receivable_open)))
                txn.write(vals)

    def action_confirm_ipc_match(self):
        """Người đối soát chốt giao dịch `matched` vào IPC đã chọn."""
        for txn in self:
            if txn.state != 'matched':
                raise UserError(_(
                    'Chỉ giao dịch "Đã khớp" mới xác nhận đối soát được.'))
            if not txn.ipc_id:
                raise UserError(_('Chọn IPC trước khi xác nhận.'))
            txn.write({
                'state': 'reconciled',
                'matched_ref': 'rp.owner.ipc,%s' % txn.ipc_id.id,
                'matched_note': _('Xác nhận tay vào IPC "%s"')
                % txn.ipc_id.name,
            })
            txn._post_ipc_received()

    def _post_ipc_received(self):
        self.ensure_one()
        self.ipc_id.message_post(body=_(
            'Nhận <b>%(amt)s</b> từ CĐT qua ngân hàng '
            '(%(bank)s, GD %(ref)s) — đã đối soát vào IPC.',
            amt='{:,.0f}'.format(self.amount),
            bank=self.bank_gateway or '', ref=self.reference_code or ''))

    def _ipc_amount_fits(self, ipc):
        """Số tiền > 0, cùng loại tiền và ≤ còn phải thu của IPC."""
        self.ensure_one()
        if self.currency_id and ipc.currency_id \
                and self.currency_id != ipc.currency_id:
            return False
        cur = ipc.currency_id or self.currency_id \
            or self.env.company.currency_id
        return (cur.compare_amounts(self.amount, 0.0) > 0
                and cur.compare_amounts(
                    self.amount, ipc.amount_receivable_open) <= 0)

    @staticmethod
    def _ipc_code_regex(name):
        """Mẫu tìm số IPC trong nội dung CK, khớp theo RANH GIỚI token.

        Tách tên thành các cụm chữ / cụm số (IPC/2026/0006 → IPC, 2026,
        0006), giữa các cụm cho phép ký tự phân cách bất kỳ hoặc không có
        — nên IPC/2026/0006, IPC20260006, IPC 2026 0006 đều khớp. Hai đầu
        không được dính tiếp cụm cùng loại: IPC_1 KHÔNG khớp trong IPC_12
        (so chuỗi con cũ khớp nhầm vì tên không đệm số 0).
        """
        tokens = re.findall(r'[^\W\d_]+|\d+', name or '')
        if not tokens:
            return None
        letter, digit = r'[^\W\d_]', r'\d'
        head = digit if tokens[0].isdigit() else letter
        tail = digit if tokens[-1].isdigit() else letter
        body = r'[\W_]*'.join(re.escape(t) for t in tokens)
        return re.compile(r'(?<!%s)%s(?!%s)' % (head, body, tail),
                          re.IGNORECASE)

    def _find_ipc_candidates(self):
        """Mọi IPC (chưa huỷ) có số xuất hiện trong code hoặc nội dung CK.

        So riêng từng ô để một mã không bị ghép nửa bên code, nửa bên
        nội dung. ⚠️ Vẫn quét mọi IPC mỗi giao dịch — nhiều IPC thì cần
        field tên chuẩn hoá + index.
        """
        self.ensure_one()
        texts = [t for t in (self.code, self.content) if t]
        found = self.env['rp.owner.ipc']
        if not texts:
            return found
        for ipc in self.env['rp.owner.ipc'].search(
                [('state', '!=', 'cancelled')]):
            rx = self._ipc_code_regex(ipc.name)
            if rx and any(rx.search(t) for t in texts):
                found |= ipc
        return found


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
