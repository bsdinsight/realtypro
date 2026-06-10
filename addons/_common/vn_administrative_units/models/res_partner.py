from odoo import api, fields, models


class ResPartner(models.Model):
    """Add Vietnamese ward and Permanent Address to partner.

    Vietnamese real estate context requires TWO addresses:
    - Contact Address (Địa chỉ liên lạc) — for mailing, notifications,
      uses the standard res.partner address fields (street, state_id,
      country_id, plus our new ward_id).
    - Permanent Address (Địa chỉ thường trú) — has legal value, used
      on contracts (HĐMB). Stored in permanent_* fields.

    Default: permanent_same_as_contact=True. When checked, permanent
    fields auto-mirror contact fields. User unticks to enter a different
    permanent address.
    """
    _inherit = 'res.partner'

    # ============================================================
    # Default country = Vietnam for new partners
    # ============================================================
    @api.model
    def default_get(self, fields_list):
        """Set country_id and permanent_country_id = Vietnam by default.

        Also default company_type = 'person' — for real estate sales,
        individual customers (Person) are the dominant case. The radio
        button widget on form view binds to company_type, not is_company.
        """
        defaults = super().default_get(fields_list)
        vn = self.env.ref('base.vn', raise_if_not_found=False)
        if vn:
            if 'country_id' in fields_list and not defaults.get('country_id'):
                defaults['country_id'] = vn.id
            if 'permanent_country_id' in fields_list and not defaults.get('permanent_country_id'):
                defaults['permanent_country_id'] = vn.id
        if 'company_type' in fields_list and not defaults.get('company_type'):
            defaults['company_type'] = 'person'
        if 'is_company' in fields_list and 'is_company' not in defaults:
            defaults['is_company'] = False
        return defaults

    # ============================================================
    # Contact Address — extend with ward
    # ============================================================
    ward_id = fields.Many2one(
        'vau.ward', string='Ward / Phường-Xã',
        domain="[('state_id', '=', state_id)]",
        help='Phường / Xã / Đặc khu - 2nd-tier Vietnamese administrative unit.',
    )

    # ============================================================
    # Permanent Address — for legal contracts
    # ============================================================
    permanent_same_as_contact = fields.Boolean(
        string='Permanent address same as contact address',
        default=True,
        help='When checked, the permanent address mirrors the contact '
             'address. Untick to enter a separate permanent address '
             '(used on legal contracts).',
    )
    permanent_country_id = fields.Many2one(
        'res.country', string='Permanent Country',
        default=lambda self: self.env.ref('base.vn', raise_if_not_found=False),
    )
    permanent_state_id = fields.Many2one(
        'res.country.state', string='Permanent Province',
        domain="[('country_id', '=', permanent_country_id)]",
    )
    permanent_ward_id = fields.Many2one(
        'vau.ward', string='Permanent Ward',
        domain="[('state_id', '=', permanent_state_id)]",
    )
    permanent_street = fields.Char(string='Permanent Street')

    # ============================================================
    # onchange logic
    # ============================================================
    @api.onchange('country_id')
    def _onchange_country_id_clear_ward(self):
        """Clear ward when country changes."""
        for partner in self:
            if partner.ward_id and partner.country_id != partner.ward_id.country_id:
                partner.ward_id = False

    @api.onchange('state_id')
    def _onchange_state_id_clear_ward(self):
        """Clear ward when state changes."""
        for partner in self:
            if partner.ward_id and partner.state_id != partner.ward_id.state_id:
                partner.ward_id = False
            self._sync_permanent_from_contact()

    @api.onchange('permanent_country_id')
    def _onchange_permanent_country_id(self):
        """Clear permanent state/ward when country changes."""
        for partner in self:
            if (partner.permanent_state_id and
                partner.permanent_state_id.country_id != partner.permanent_country_id):
                partner.permanent_state_id = False
                partner.permanent_ward_id = False

    @api.onchange('permanent_state_id')
    def _onchange_permanent_state_id(self):
        """Clear permanent ward when state changes."""
        for partner in self:
            if (partner.permanent_ward_id and
                partner.permanent_ward_id.state_id != partner.permanent_state_id):
                partner.permanent_ward_id = False

    @api.onchange('permanent_same_as_contact', 'country_id', 'state_id',
                  'ward_id', 'street')
    def _onchange_sync_permanent(self):
        """When 'same as contact' is on, mirror permanent fields from contact.

        Triggers also when contact address fields change, so permanent
        stays in sync automatically.
        """
        for partner in self:
            if partner.permanent_same_as_contact:
                partner.permanent_country_id = partner.country_id
                partner.permanent_state_id = partner.state_id
                partner.permanent_ward_id = partner.ward_id
                partner.permanent_street = partner.street

    def _sync_permanent_from_contact(self):
        """Helper: copy contact → permanent when same_as_contact is True."""
        self.ensure_one()
        if self.permanent_same_as_contact:
            self.permanent_country_id = self.country_id
            self.permanent_state_id = self.state_id
            self.permanent_ward_id = self.ward_id
            self.permanent_street = self.street

    # ============================================================
    # Server-side enforcement (in case onchange isn't triggered)
    # ============================================================
    @api.model_create_multi
    def create(self, vals_list):
        """If same_as_contact, sync permanent from contact at create time."""
        for vals in vals_list:
            if vals.get('permanent_same_as_contact', True):
                vals.setdefault('permanent_country_id', vals.get('country_id'))
                vals.setdefault('permanent_state_id', vals.get('state_id'))
                vals.setdefault('permanent_ward_id', vals.get('ward_id'))
                vals.setdefault('permanent_street', vals.get('street'))
        return super().create(vals_list)

    def write(self, vals):
        """Sync permanent fields if same_as_contact stays True."""
        res = super().write(vals)
        # If any contact address field changed, re-sync permanent
        contact_fields = {'country_id', 'state_id', 'ward_id', 'street'}
        if contact_fields & set(vals.keys()):
            for partner in self:
                if partner.permanent_same_as_contact:
                    super(ResPartner, partner).write({
                        'permanent_country_id': partner.country_id.id,
                        'permanent_state_id': partner.state_id.id,
                        'permanent_ward_id': partner.ward_id.id,
                        'permanent_street': partner.street,
                    })
        return res
