from odoo import api, fields, models


VIEW_TYPE_SELECTION = [
    ('lake', 'Lake View'), ('river', 'River View'),
    ('sea', 'Sea View'), ('mountain', 'Mountain View'),
    ('city', 'City View'), ('park', 'Park View'),
    ('pool', 'Pool View'), ('internal', 'Internal View'),
    ('garden', 'Garden View'), ('other', 'Other'),
]


class ReUnitType(models.Model):
    _name = 're.unit.type'
    _description = 'Real Estate Unit Type'
    _order = 'sequence, name'

    name = fields.Char(string='Unit Type Name', required=True, translate=True)
    code = fields.Char(string='Code', required=True)
    sequence = fields.Integer(default=10)

    category = fields.Selection(
        [('apartment', 'Apartment'), ('studio', 'Studio'),
         ('duplex', 'Duplex'), ('penthouse', 'Penthouse'),
         ('shophouse', 'Shophouse'), ('villa', 'Villa'),
         ('townhouse', 'Townhouse'), ('officetel', 'Officetel'),
         ('loft', 'Loft'), ('condotel', 'Condotel'),
         ('mini_hotel', 'Mini Hotel'), ('other', 'Other')],
        string='Category', default='apartment', required=True,
    )

    default_bedroom_count = fields.Integer(string='Default Bedrooms')
    default_bathroom_count = fields.Integer(string='Default Bathrooms')
    default_balcony_count = fields.Integer(string='Default Balconies')
    default_area_min = fields.Float(string='Min Area (m²)', digits=(10, 2))
    default_area_max = fields.Float(string='Max Area (m²)', digits=(10, 2))
    default_view_type = fields.Selection(VIEW_TYPE_SELECTION, string='Default View')

    color = fields.Integer(string='Color Index')
    icon = fields.Char(string='Icon')
    image = fields.Image(string='Layout Sample', max_width=1920, max_height=1080)

    is_residential = fields.Boolean(string='Residential', default=True)
    is_corner = fields.Boolean(string='Corner Type')
    requires_furniture = fields.Boolean(string='Furniture Included')

    tagline = fields.Char(string='Tagline', translate=True)
    target_segment = fields.Selection(
        [('single', 'Single'), ('couple', 'Couple'),
         ('small_family', 'Small Family (3-4)'),
         ('large_family', 'Large Family (5+)'),
         ('investor', 'Investor')],
        string='Target Segment',
    )

    description = fields.Text(string='Description', translate=True)
    active = fields.Boolean(default=True)

    _unique_code = models.Constraint('UNIQUE(code)', 'Unit type code must be unique!')
