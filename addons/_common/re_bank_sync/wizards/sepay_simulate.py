# -*- coding: utf-8 -*-
"""Mô phỏng giao dịch SePay — để DEMO tự chứa.

Không cần tài khoản ngân hàng thật, không cần SePay account: wizard dựng
payload đúng dạng SePay rồi đưa thẳng vào sổ đệm qua `ingest()` (cùng đường
webhook thật đi). Khách bấm nút → giao dịch hiện ra → tự khớp IPC.

(Bản "thật" của cái này là SePay Test mode: sandbox mô phỏng → bắn webhook
tới /sepay/webhook. Wizard này là bản offline, không phụ thuộc mạng.)
"""
import time

from odoo import _, fields, models


class SePaySimulateWizard(models.TransientModel):
    _name = 're.bank.sepay.simulate.wizard'
    _description = 'Mô phỏng giao dịch SePay (demo)'

    bank_gateway = fields.Char(string='Ngân hàng', default='MBBank')
    account_number = fields.Char(string='Số tài khoản', default='0123456789')
    direction = fields.Selection([
        ('in', 'Tiền vào'),
        ('out', 'Tiền ra'),
    ], string='Chiều', default='in', required=True)
    amount = fields.Monetary(string='Số tiền', required=True)
    currency_id = fields.Many2one(
        'res.currency', default=lambda s: s.env.company.currency_id)
    content = fields.Char(
        string='Nội dung CK', required=True,
        help='VD: "IPC0006 CDT thanh toan dot 1" — mã IPC trong nội dung sẽ '
             'được tự khớp.')
    code = fields.Char(string='Mã (code)',
                       help='Mã thanh toán SePay tách được (thường = mã IPC).')

    def action_simulate(self):
        self.ensure_one()
        # id giả lập duy nhất (khỏi trùng), không dùng Date.now trong test
        ext = 'SIM%d' % int(time.time() * 1000)
        payload = {
            'id': ext, 'gateway': self.bank_gateway,
            'accountNumber': self.account_number,
            'transferType': self.direction,
            'transferAmount': self.amount,
            'content': self.content, 'code': self.code or '',
            'referenceCode': ext, 'accumulated': 0,
        }
        import json
        rec, created = self.env['re.bank.transaction'].sudo().ingest({
            'source': 'sepay', 'external_id': ext,
            'bank_gateway': self.bank_gateway,
            'account_number': self.account_number,
            'direction': self.direction, 'amount': self.amount,
            'content': self.content, 'code': self.code,
            'reference_code': ext,
            'raw_payload': json.dumps(payload, ensure_ascii=False),
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 're.bank.transaction',
            'res_id': rec.id,
            'view_mode': 'form',
            'target': 'current',
        }
