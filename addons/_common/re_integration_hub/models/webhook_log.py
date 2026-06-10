# -*- coding: utf-8 -*-
"""
re.webhook.log — append-only audit log of inbound webhook events.

Outbound deliveries already live in re.webhook.outbound. This model
stores everything that arrived at our doorstep, whether or not the
handler processed it successfully. Useful for forensic debugging and
for retrying a handler against a stored payload.
"""
from odoo import api, fields, models


class ReWebhookLog(models.Model):
    _name = 're.webhook.log'
    _description = 'Inbound Webhook Log'
    _order = 'create_date desc, id desc'

    event_id = fields.Char(required=True, index=True, readonly=True)
    event_name = fields.Char(required=True, index=True, readonly=True)
    received_at = fields.Datetime(default=fields.Datetime.now, readonly=True)

    api_key_id = fields.Many2one(
        're.api.key', string='Authenticated As', readonly=True, ondelete='set null',
    )
    remote_addr = fields.Char(readonly=True)
    headers_json = fields.Text(string='Headers', readonly=True)
    payload_json = fields.Text(string='Payload', readonly=True)

    state = fields.Selection(
        [('received', 'Received (not handled)'),
         ('handled', 'Handled OK'),
         ('rejected', 'Rejected (auth/sig)'),
         ('error', 'Handler Error'),
         ('duplicate', 'Duplicate Ignored')],
        default='received', required=True, index=True,
    )
    handler_name = fields.Char(readonly=True)
    error = fields.Text(readonly=True)

    _event_id_uniq = models.Constraint(
        'unique (event_id, event_name)',
        'Idempotency key collision: this event has already been logged.',
    )

    @api.model
    def already_processed(self, event_id, event_name):
        """Return True if a handled or duplicate row exists for this id."""
        return bool(self.search_count([
            ('event_id', '=', event_id),
            ('event_name', '=', event_name),
            ('state', 'in', ['handled', 'duplicate']),
        ]))
