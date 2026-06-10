# -*- coding: utf-8 -*-
"""
re.api.key — issue, rotate, revoke API keys for inter-app webhooks.

The key is shown ONCE at creation time (the user must copy it to the
peer system). Internally we store only a SHA-256 hash, so a leaked
database backup does not expose live keys.
"""
import hashlib
import secrets

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ReApiKey(models.Model):
    _name = 're.api.key'
    _description = 'Realty API Key'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(
        required=True, tracking=True,
        help='Human label, e.g. "From rp_capitaland_project (handover)".',
    )
    consumer = fields.Char(
        string='Consumer Identifier',
        required=True, tracking=True,
        help='Stable slug identifying who uses this key. Convention: '
             '<source_app>.<source_db>, e.g. "project.capitaland_project".',
    )

    # The plaintext key is shown ONCE on creation, then forgotten.
    key_preview = fields.Char(
        string='Key Preview', readonly=True, copy=False,
        help='Last 8 characters of the key, for visual identification. '
             'The full key is never stored.',
    )
    key_hash = fields.Char(
        string='Key Hash (SHA-256)', readonly=True, copy=False, index=True,
    )

    state = fields.Selection(
        [('active', 'Active'), ('revoked', 'Revoked')],
        default='active', required=True, tracking=True,
    )
    last_used = fields.Datetime(string='Last Used', readonly=True)
    use_count = fields.Integer(string='Uses', default=0, readonly=True)
    expires_at = fields.Datetime(
        string='Expires At', tracking=True,
        help='Optional. Past this point the key is rejected.',
    )
    notes = fields.Text()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        """Generate a fresh secret for each new record.

        We mutate `vals_list` to include the hash + preview, then
        attach the plaintext to a context-local list so the caller
        (typically a wizard or button) can read it.
        """
        records = self.browse()
        plaintexts = []
        for vals in vals_list:
            plaintext = secrets.token_urlsafe(48)  # ~64 chars
            vals['key_hash'] = self._hash(plaintext)
            vals['key_preview'] = plaintext[-8:]
            plaintexts.append(plaintext)
        records = super().create(vals_list)
        # Store the plaintexts so the caller can show them once.
        # We attach to env (transactional) so they're scoped to the call.
        cache = self.env.context.get('_re_api_key_plaintexts', None)
        if isinstance(cache, list):
            cache.extend(plaintexts)
        else:
            self = self.with_context(_re_api_key_plaintexts=plaintexts)
            records = records.with_context(
                _re_api_key_plaintexts=plaintexts
            )
        return records

    def action_revoke(self):
        for rec in self:
            rec.state = 'revoked'
            rec.message_post(body=_('Key revoked.'))

    def action_rotate(self):
        """Issue a new secret on the same record. The old hash is
        overwritten — the previous key stops working immediately."""
        for rec in self:
            new_plain = secrets.token_urlsafe(48)
            rec.key_hash = self._hash(new_plain)
            rec.key_preview = new_plain[-8:]
            rec.state = 'active'
            rec.message_post(body=_('Key rotated. New preview: ...%s') % rec.key_preview)
            # In a real UI we'd return an action that displays the new
            # plaintext via a wizard. For now, the caller reads it from
            # the context cache.
            cache = self.env.context.get('_re_api_key_plaintexts', None)
            if isinstance(cache, list):
                cache.append(new_plain)

    # ------------------------------------------------------------------
    # Lookup helpers
    # ------------------------------------------------------------------
    @api.model
    def authenticate(self, plaintext_key):
        """Return the matching active API key record, or empty recordset.

        Used by inbound webhook controllers. Increments use_count.
        """
        if not plaintext_key:
            return self.browse()
        hashed = self._hash(plaintext_key)
        match = self.sudo().search([
            ('key_hash', '=', hashed),
            ('state', '=', 'active'),
        ], limit=1)
        if not match:
            return match
        # Expiry check
        now = fields.Datetime.now()
        if match.expires_at and match.expires_at < now:
            return match.browse()
        match.sudo().write({
            'last_used': now,
            'use_count': match.use_count + 1,
        })
        return match

    @staticmethod
    def _hash(plaintext):
        return hashlib.sha256(plaintext.encode('utf-8')).hexdigest()
