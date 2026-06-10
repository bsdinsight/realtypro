from odoo import api, fields, models


class VauWard(models.Model):
    """Vietnamese Ward / Commune / Special Zone (Phường, Xã, Đặc khu).

    The 2nd-tier administrative unit in Vietnam after the 2025 reform.
    Each ward belongs to one province (state_id).

    Total: 3,321 wards as of Decree 19/2025/QĐ-TTg.
    """
    _name = 'vau.ward'
    _description = 'Vietnamese Ward / Commune'
    _order = 'state_id, name'
    _rec_name = 'full_name'

    code = fields.Char(
        string='Code', required=True, copy=False,
        help='Official GSO code (e.g. "00004" for Phường Ba Đình)',
    )
    name = fields.Char(
        string='Short Name', required=True, translate=False,
        help='Short name without prefix (e.g. "Ba Đình")',
    )
    name_en = fields.Char(string='Name (English)', translate=False)
    full_name = fields.Char(
        string='Full Name', required=True, translate=False,
        help='Full Vietnamese name with prefix (e.g. "Phường Ba Đình")',
    )
    full_name_en = fields.Char(string='Full Name (English)', translate=False)
    code_name = fields.Char(string='Code Name (slug)')

    state_id = fields.Many2one(
        'res.country.state', string='Province',
        required=True, ondelete='restrict',
        domain="[('country_id.code', '=', 'VN')]",
    )
    country_id = fields.Many2one(
        related='state_id.country_id', store=True, readonly=True,
    )

    active = fields.Boolean(default=True)

    _unique_code = models.Constraint(
        'unique(code)',
        'Ward code must be unique.',
    )

    def name_get(self):
        # Default rec_name = full_name; fallback to name if missing
        return [(rec.id, rec.full_name or rec.name) for rec in self]

    @api.model
    def _name_search(self, name='', domain=None, operator='ilike',
                     limit=100, order=None):
        """Allow searching by name, full_name, or name_en."""
        domain = list(domain or [])
        if name:
            domain = ['|', '|',
                      ('full_name', operator, name),
                      ('name', operator, name),
                      ('name_en', operator, name)] + domain
        return self._search(domain, limit=limit, order=order)
