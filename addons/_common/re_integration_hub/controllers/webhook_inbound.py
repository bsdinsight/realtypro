# -*- coding: utf-8 -*-
"""
Inbound webhook receiver.

POST /realtypro/webhook/<event_name>
    Headers:
        Authorization: Bearer <api_key_plaintext>
        X-Realty-Event-Id: <unique-id>
        X-Realty-Timestamp: <unix-seconds>
        X-Realty-Signature: sha256=<hex>      (optional but recommended)
    Body: JSON

App modules register handlers by populating the
``re.integration.handlers`` registry on the env (see
``register_handler`` below). Handlers receive the parsed payload and a
record of the originating webhook log row.
"""
import hashlib
import hmac
import json
import logging
import time
from typing import Callable

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

# Maximum age (seconds) of a request based on its X-Realty-Timestamp.
# Beyond this we reject as a replay attack guard.
TIMESTAMP_TOLERANCE = 5 * 60

# Module-level registry of inbound handlers, keyed by event_name.
# Filled by app modules at import time:
#
#     from odoo.addons.re_integration_hub.controllers.webhook_inbound \
#         import register_handler
#     register_handler('project.handover.completed', my_handler)
#
# A handler signature is: handler(env, payload: dict, log: re.webhook.log) -> None
#
# This is process-wide, NOT per-database. That's OK because handlers
# are typically defined in modules whose presence is what selects them
# (the module is only installed in DBs that should react to the event).
_HANDLERS: dict[str, Callable] = {}


def register_handler(event_name: str, fn: Callable) -> None:
    """Register a function to handle ``event_name`` inbound events."""
    if event_name in _HANDLERS:
        _logger.warning('Webhook handler for %r overridden', event_name)
    _HANDLERS[event_name] = fn


class WebhookInbound(http.Controller):

    @http.route('/realtypro/webhook/<string:event_name>',
                type='http', auth='public', methods=['POST'], csrf=False)
    def receive(self, event_name, **kw):
        """Authenticate, verify, log, dispatch.

        Returns 2xx on accepted (even if handler errors — handler errors
        produce a logged row that admins can replay), 4xx on auth /
        signature / format failures.
        """
        # 1. Pull headers we care about
        h = request.httprequest.headers
        bearer = h.get('Authorization', '')
        api_key = bearer.removeprefix('Bearer ').strip() if bearer else ''
        event_id = h.get('X-Realty-Event-Id', '').strip()
        ts_header = h.get('X-Realty-Timestamp', '').strip()
        sig_header = h.get('X-Realty-Signature', '').strip()

        if not event_id:
            return _resp({'error': 'missing X-Realty-Event-Id'}, 400)

        # 2. Authenticate the API key
        key = request.env['re.api.key'].sudo().authenticate(api_key)
        if not key:
            _logger.warning('Webhook rejected: bad/expired key for %s', event_name)
            return _resp({'error': 'unauthenticated'}, 401)

        # 3. Verify timestamp window (replay guard)
        try:
            req_ts = int(ts_header)
        except ValueError:
            return _resp({'error': 'bad X-Realty-Timestamp'}, 400)
        now = int(time.time())
        if abs(now - req_ts) > TIMESTAMP_TOLERANCE:
            return _resp({'error': 'timestamp out of range'}, 400)

        # 4. Read body and verify signature, if a signature was sent
        raw = request.httprequest.get_data() or b''
        if sig_header:
            secret = request.env['ir.config_parameter'].sudo().get_param(
                f're.api.key.secret.{key.id}'
            )
            if not secret:
                _logger.warning('Webhook %s: signature provided but no secret '
                                'configured for key %s', event_name, key.id)
                return _resp({'error': 'server signature key missing'}, 500)
            if not _verify_signature(secret, ts_header, raw, sig_header):
                _logger.warning('Webhook %s: signature mismatch from %s',
                                event_name, request.httprequest.remote_addr)
                request.env['re.webhook.log'].sudo().create({
                    'event_id': event_id,
                    'event_name': event_name,
                    'api_key_id': key.id,
                    'remote_addr': request.httprequest.remote_addr,
                    'headers_json': _headers_to_json(h),
                    'payload_json': raw.decode('utf-8', errors='replace')[:10000],
                    'state': 'rejected',
                    'error': 'signature mismatch',
                })
                return _resp({'error': 'bad signature'}, 401)

        # 5. Parse JSON
        try:
            payload = json.loads(raw.decode('utf-8')) if raw else {}
        except (ValueError, UnicodeDecodeError) as exc:
            return _resp({'error': f'invalid json: {exc}'}, 400)

        # 6. Idempotency
        Log = request.env['re.webhook.log'].sudo()
        if Log.already_processed(event_id, event_name):
            Log.create({
                'event_id': event_id + '-dup',
                'event_name': event_name,
                'api_key_id': key.id,
                'state': 'duplicate',
                'remote_addr': request.httprequest.remote_addr,
                'payload_json': raw.decode('utf-8', errors='replace')[:10000],
            })
            return _resp({'status': 'duplicate ignored'}, 200)

        # 7. Persist log row first (so we have a record even if handler
        # crashes)
        log = Log.create({
            'event_id': event_id,
            'event_name': event_name,
            'api_key_id': key.id,
            'remote_addr': request.httprequest.remote_addr,
            'headers_json': _headers_to_json(h),
            'payload_json': raw.decode('utf-8', errors='replace')[:10000],
            'state': 'received',
        })

        # 8. Dispatch to handler if any
        handler = _HANDLERS.get(event_name)
        if not handler:
            return _resp({'status': 'received', 'handled': False,
                          'note': 'no handler registered'}, 202)

        try:
            handler(request.env, payload, log)
        except Exception as exc:
            _logger.exception('Webhook handler %r raised', event_name)
            log.write({'state': 'error', 'handler_name': handler.__qualname__,
                       'error': repr(exc)})
            # We still return 200 — sender shouldn't keep retrying a
            # handler bug. Admin can replay manually.
            return _resp({'status': 'received', 'handled': False,
                          'error': repr(exc)}, 200)

        log.write({'state': 'handled', 'handler_name': handler.__qualname__})
        return _resp({'status': 'handled'}, 200)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _verify_signature(secret: str, ts: str, body: bytes, header: str) -> bool:
    """Constant-time compare against the expected HMAC."""
    if not header.startswith('sha256='):
        return False
    given = header[len('sha256='):]
    expected = hmac.new(
        secret.encode('utf-8'),
        msg=f'{ts}.'.encode('utf-8') + body,
        digestmod=hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(given, expected)


def _headers_to_json(headers) -> str:
    # Strip the Authorization header to avoid leaking keys into the log.
    safe = {k: v for k, v in headers.items()
            if k.lower() not in ('authorization', 'cookie')}
    return json.dumps(safe, ensure_ascii=False)


def _resp(payload, status):
    return request.make_response(
        json.dumps(payload, ensure_ascii=False),
        headers=[('Content-Type', 'application/json; charset=utf-8')],
        status=status,
    )
