from odoo import api, fields, models


class CrmLead(models.Model):
    """Add Vietnamese ward to CRM lead address.

    Lead has only ONE address (the contact mailing address) — no
    permanent vs contact distinction. When the lead is converted to
    an opportunity / partner, the address fields populate the
    res.partner directly.
    """
    _inherit = 'crm.lead'

    ward_id = fields.Many2one(
        'vau.ward', string='Ward / Phường-Xã',
        domain="[('state_id', '=', state_id)]",
        help='Phường / Xã / Đặc khu - 2nd-tier Vietnamese administrative unit.',
    )

    @api.onchange('country_id')
    def _onchange_country_id_clear_ward_lead(self):
        """Clear ward when country changes."""
        for lead in self:
            if lead.ward_id and lead.country_id != lead.ward_id.country_id:
                lead.ward_id = False

    @api.onchange('state_id')
    def _onchange_state_id_clear_ward_lead(self):
        """Clear ward when state changes."""
        for lead in self:
            if lead.ward_id and lead.state_id != lead.ward_id.state_id:
                lead.ward_id = False

    @api.model
    def default_get(self, fields_list):
        """Default country = Vietnam for new leads."""
        defaults = super().default_get(fields_list)
        if 'country_id' in fields_list and not defaults.get('country_id'):
            vn = self.env.ref('base.vn', raise_if_not_found=False)
            if vn:
                defaults['country_id'] = vn.id
        return defaults

    def _prepare_customer_values(self, partner_name, is_company=False, parent_id=False):
        """When converting lead → partner, propagate ward_id."""
        vals = super()._prepare_customer_values(
            partner_name, is_company=is_company, parent_id=parent_id,
        )
        if self.ward_id:
            vals['ward_id'] = self.ward_id.id
        return vals
