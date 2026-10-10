# -*- coding: utf-8 -*-
"""Mô phỏng giao dịch SePay — để DEMO tự chứa.

Không cần tài khoản ngân hàng thật, không cần SePay account: wizard dựng
payload đúng dạng SePay rồi đưa thẳng vào sổ đệm qua `ingest()` (cùng đường
webhook thật đi). Khách bấm nút → giao dịch hiện ra → tự khớp IPC.

(Bản "thật" của cái này là SePay Test mode: sandbox mô phỏng → bắn webhook
tới /sepay/webhook. Wizard này là bản offline, không phụ thuộc mạng.)

Giao dịch mô phỏng đi thẳng vào đối soát: khớp IPC → IPC ghi đã thu → định
giá lại TSBĐ quyền đòi nợ. Vì vậy nó bị khoá 3 lớp:
- chỉ Integration Admin / quản trị hệ thống (ACL + kiểm lại trong action,
  vì `ingest()` chạy sudo);
- chỉ trên DB demo (tham số `realtypro.is_demo`, do script dựng demo đặt);
- nguồn riêng `demo_simulate`, không giả làm `sepay`.
"""
import json
import time

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import str2bool

DEMO_PARAM = 'realtypro.is_demo'
SIMULATE_GROUPS = (
    're_integration_hub.group_integration_admin',
    'base.group_system',
)


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

    @api.model
    def _simulation_enabled(self):
        return str2bool(self.env['ir.config_parameter'].sudo().get_param(
            DEMO_PARAM, 'False'), default=False)

    def _check_can_simulate(self):
        if not self.env.su and not any(
                self.env.user.has_group(g) for g in SIMULATE_GROUPS):
            raise AccessError(_(
                'Chỉ Integration Admin hoặc quản trị hệ thống được mô phỏng '
                'giao dịch ngân hàng.'))
        if not self._simulation_enabled():
            raise UserError(_(
                'Mô phỏng giao dịch chỉ bật trên DB demo (tham số hệ thống '
                '%s). Trên DB thật, giao dịch giả sẽ tự đối soát vào IPC '
                'thật và làm sai giá trị tài sản bảo đảm.', DEMO_PARAM))

    def action_simulate(self):
        self.ensure_one()
        self._check_can_simulate()
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
        rec, created = self.env['re.bank.transaction'].sudo().ingest({
            'source': 'demo_simulate', 'external_id': ext,
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
