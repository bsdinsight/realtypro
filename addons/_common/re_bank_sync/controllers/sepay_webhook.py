# -*- coding: utf-8 -*-
"""Webhook nhận giao dịch từ SePay.

SePay có giao thức CỐ ĐỊNH riêng (không bẻ theo hub được):
- Gửi `Authorization: Apikey <key>` (quy ước SePay).
- event id nằm trong payload `id`.
- Endpoint PHẢI trả HTTP 200/201 kèm `{"success": true}` thì SePay mới ghi
  nhận thành công (nếu không, SePay retry).

Nên controller riêng, nhưng TÁI DÙNG hạ tầng re_integration_hub:
- `re.webhook.log` — chống trùng + lưu vết (kể cả khi handler lỗi).
- `re.api.key` — xác thực key (băm, có thể xoay/thu hồi).

Payload SePay:
  {"id":12345,"gateway":"MBBank","transactionDate":"2025-01-15 10:30:00",
   "accountNumber":"0123456789","code":"DH123456","content":"...",
   "transferType":"in","transferAmount":100000,"referenceCode":"FT...",
   "accumulated":5000000}
"""
import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

EVENT_NAME = 'sepay'


def _resp(payload, status=200):
    return request.make_json_response(payload, status=status)


class SePayWebhookController(http.Controller):

    @http.route('/sepay/webhook', type='http', auth='public',
                methods=['POST'], csrf=False, save_session=False)
    def sepay_webhook(self, **kw):
        # 1. Xác thực: SePay gửi 'Authorization: Apikey <key>'
        auth = request.httprequest.headers.get('Authorization', '')
        api_key = ''
        if auth.lower().startswith('apikey '):
            api_key = auth[7:].strip()
        elif auth.lower().startswith('bearer '):
            api_key = auth[7:].strip()
        key = request.env['re.api.key'].sudo().authenticate(api_key)
        if not key:
            # cho phép cấu hình 1 key demo qua param (test mode)
            demo = request.env['ir.config_parameter'].sudo().get_param(
                'sepay.webhook.token')
            if not (demo and api_key and api_key == demo):
                return _resp({'success': False, 'error': 'unauthorized'}, 401)

        # 2. Đọc payload
        raw = request.httprequest.get_data() or b''
        try:
            payload = json.loads(raw.decode('utf-8')) if raw else {}
        except (ValueError, UnicodeDecodeError) as exc:
            return _resp({'success': False, 'error': 'invalid json: %s' % exc},
                         400)

        event_id = str(payload.get('id') or '').strip()
        if not event_id:
            return _resp({'success': False, 'error': 'missing id'}, 400)

        Log = request.env['re.webhook.log'].sudo()
        # 3. Chống trùng — SePay có thể bắn lại
        if Log.already_processed(event_id, EVENT_NAME):
            return _resp({'success': True, 'note': 'duplicate ignored'}, 200)

        # 4. Lưu log trước (có vết kể cả khi tạo giao dịch lỗi)
        log = Log.create({
            'event_id': event_id,
            'event_name': EVENT_NAME,
            'api_key_id': key.id if key else False,
            'remote_addr': request.httprequest.remote_addr,
            'payload_json': raw.decode('utf-8', errors='replace')[:10000],
            'state': 'received',
        })

        # 5. Đưa vào sổ đệm (dedup lần 2 theo external_id)
        try:
            rec, created = request.env['re.bank.transaction'].sudo()\
                .ingest(self._to_txn_vals(payload))
        except Exception as exc:  # noqa: BLE001
            _logger.exception('SePay ingest failed')
            log.write({'state': 'error', 'error': repr(exc)})
            # vẫn trả success để SePay khỏi retry vào bug — admin replay tay
            return _resp({'success': True, 'note': 'logged, ingest error'}, 200)

        log.write({'state': 'handled',
                   'handler_name': 're.bank.transaction.ingest'})
        return _resp({'success': True, 'transaction_id': rec.id,
                      'created': created}, 200)

    @staticmethod
    def _to_txn_vals(p):
        """Payload SePay → vals re.bank.transaction."""
        direction = 'in' if (p.get('transferType') or '').lower() == 'in' \
            else 'out'
        return {
            'source': 'sepay',
            'external_id': str(p.get('id') or ''),
            'bank_gateway': p.get('gateway'),
            'account_number': p.get('accountNumber'),
            'txn_date': (p.get('transactionDate') or '').replace('T', ' ')[:19]
                        or False,
            'direction': direction,
            'amount': abs(float(p.get('transferAmount') or 0)),
            'content': p.get('content'),
            'code': p.get('code'),
            'reference_code': p.get('referenceCode'),
            'accumulated': float(p.get('accumulated') or 0),
            'raw_payload': json.dumps(p, ensure_ascii=False),
        }
