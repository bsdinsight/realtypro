# -*- coding: utf-8 -*-
"""
re.webhook.outbound — queue + sender for outbound RealtyPro webhooks.

Application code that wants to notify another database calls
``self.env['re.webhook.outbound'].emit(event, payload, target_url, ...)``.
The record is inserted in state ``pending``; a cron picks it up,
delivers it with HMAC signing, and marks the result.

Retry policy: exponential backoff capped at 1 hour. After 8 failed
attempts the row goes to state ``dead`` and an activity is scheduled
for the integration admin.
"""
import hashlib
import hmac
import json
import logging
import secrets
from datetime import datetime, timedelta

import requests
from requests.exceptions import RequestException

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 8
# Backoff schedule (seconds). After attempt N, wait BACKOFF[min(N, len-1)]
# before retry. Caps at 1 hour for tail attempts.
BACKOFF_SECONDS = [10, 30, 120, 300, 900, 1800, 3600, 3600]


class ReWebhookOutbound(models.Model):
    _name = 're.webhook.outbound'
    _description = 'Outbound Webhook Event'
    _inherit = ['mail.thread']
    _order = 'create_date desc, id desc'

    # Identity
    event_id = fields.Char(
        string='Event ID', required=True, readonly=True, index=True, copy=False,
        default=lambda self: secrets.token_urlsafe(16),
        help='Receiver-side idempotency key. Two posts of the same event '
             'must produce identical effects.',
    )
    event_name = fields.Char(
        required=True, tracking=True,
        help='Dotted name, e.g. "project.handover.completed". Receivers '
             'route by this string.',
    )
    payload_json = fields.Text(
        string='Payload (JSON)', required=True,
        help='Pre-serialized JSON. Stored as text rather than a JSON '
             'column so we can also support legacy Postgres versions.',
    )

    # Delivery target
    target_url = fields.Char(string='Target URL', required=True, tracking=True)
    api_key_id = fields.Many2one(
        're.api.key', string='Signing Key',
        ondelete='restrict',
        help='The receiver looks up this key by hash; the sender uses '
             'its plaintext to compute the HMAC signature. Plaintext is '
             'NOT stored on the webhook row — we look it up at send time '
             'from a secure parameter.',
    )

    # State
    state = fields.Selection(
        [('pending', 'Pending'),
         ('sent', 'Sent'),
         ('failed', 'Retrying'),
         ('dead', 'Dead Letter')],
        default='pending', required=True, tracking=True, index=True,
    )
    attempts = fields.Integer(default=0, readonly=True)
    next_attempt_at = fields.Datetime(default=fields.Datetime.now, index=True)
    last_attempt_at = fields.Datetime(readonly=True)
    last_response_code = fields.Integer(readonly=True)
    last_error = fields.Text(readonly=True)

    # ------------------------------------------------------------------
    # Public API for app modules
    # ------------------------------------------------------------------
    @api.model
    def emit(self, event_name, payload, target_url, api_key=None, event_id=None):
        """Queue a webhook for delivery.

        :param event_name: dotted event identifier
        :param payload: dict or JSON-serializable structure
        :param target_url: full URL to POST to
        :param api_key: re.api.key recordset or id (optional)
        :param event_id: explicit id for idempotency (optional)
        :returns: the created re.webhook.outbound record
        """
        vals = {
            'event_name': event_name,
            'payload_json': json.dumps(payload, ensure_ascii=False, default=str),
            'target_url': target_url,
        }
        if event_id:
            vals['event_id'] = event_id
        if api_key:
            if isinstance(api_key, int):
                vals['api_key_id'] = api_key
            else:
                vals['api_key_id'] = api_key.id
        rec = self.create(vals)
        _logger.info('Queued webhook %s -> %s (event_id=%s)',
                     event_name, target_url, rec.event_id)
        return rec

    # ------------------------------------------------------------------
    # Sender (called by cron)
    # ------------------------------------------------------------------
    @api.model
    def cron_send_pending(self):
        """Cron entry. Sends all rows whose next_attempt_at has passed."""
        now = fields.Datetime.now()
        domain = [
            ('state', 'in', ['pending', 'failed']),
            ('next_attempt_at', '<=', now),
        ]
        # Process in small batches to bound transaction time.
        ready = self.search(domain, limit=50, order='next_attempt_at asc')
        for rec in ready:
            try:
                rec._deliver()
            except Exception:
                # Defensive — _deliver already records errors per row;
                # this catch ensures one bad row doesn't abort the cron.
                _logger.exception('Webhook %s delivery raised', rec.id)

    def _deliver(self):
        self.ensure_one()
        self.attempts += 1
        self.last_attempt_at = fields.Datetime.now()

        # Retrieve the plaintext signing key. We store it under
        # ir.config_parameter keyed by api_key.id; senders set it at
        # creation time and rotate it via the key UI.
        secret = None
        if self.api_key_id:
            param = f're.api.key.secret.{self.api_key_id.id}'
            secret = self.env['ir.config_parameter'].sudo().get_param(param)

        body = self.payload_json or '{}'
        timestamp = str(int(datetime.utcnow().timestamp()))
        headers = {
            'Content-Type': 'application/json; charset=utf-8',
            'X-Realty-Event': self.event_name,
            'X-Realty-Event-Id': self.event_id,
            'X-Realty-Timestamp': timestamp,
        }
        if secret:
            mac = hmac.new(
                secret.encode('utf-8'),
                msg=f'{timestamp}.{body}'.encode('utf-8'),
                digestmod=hashlib.sha256,
            ).hexdigest()
            headers['X-Realty-Signature'] = f'sha256={mac}'

        try:
            r = requests.post(self.target_url, data=body.encode('utf-8'),
                              headers=headers, timeout=15)
        except RequestException as exc:
            self._record_failure(0, repr(exc))
            return

        self.last_response_code = r.status_code
        if 200 <= r.status_code < 300:
            self.state = 'sent'
            self.last_error = False
            _logger.info('Webhook %s delivered (%s)', self.event_id, r.status_code)
        elif r.status_code in (400, 401, 403, 404, 410):
            # Permanent client errors — do not retry.
            self._record_failure(r.status_code, r.text[:1000], dead=True)
        else:
            self._record_failure(r.status_code, r.text[:1000])

    def _record_failure(self, code, message, dead=False):
        self.last_response_code = code
        self.last_error = message
        if dead or self.attempts >= MAX_ATTEMPTS:
            self.state = 'dead'
            self.activity_schedule(
                'mail.mail_activity_data_warning',
                summary=_('Webhook %s failed permanently') % self.event_name,
                note=_('After %s attempts the webhook still cannot deliver. '
                       'Investigate target_url=%s, last error: %s') % (
                    self.attempts, self.target_url, message),
            )
        else:
            self.state = 'failed'
            wait = BACKOFF_SECONDS[min(self.attempts, len(BACKOFF_SECONDS) - 1)]
            self.next_attempt_at = fields.Datetime.now() + timedelta(seconds=wait)

    # ------------------------------------------------------------------
    # Manual actions
    # ------------------------------------------------------------------
    def action_retry_now(self):
        for rec in self:
            rec.state = 'pending'
            rec.next_attempt_at = fields.Datetime.now()
            rec.message_post(body=_('Manually re-queued.'))

    def action_mark_dead(self):
        for rec in self:
            rec.state = 'dead'
            rec.message_post(body=_('Manually marked as dead letter.'))
