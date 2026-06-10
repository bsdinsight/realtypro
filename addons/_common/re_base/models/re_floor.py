from odoo import api, fields, models


class ReFloor(models.Model):
    _name = 're.floor'
    _description = 'Real Estate Floor'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'building_id, floor_number'

    name = fields.Char(string='Floor Name', required=True, tracking=True)
    code = fields.Char(string='Code', required=True)
    floor_number = fields.Integer(string='Floor Number', required=True, default=1)

    building_id = fields.Many2one('re.building', string='Building', required=True,
                                   tracking=True, ondelete='cascade')
    project_id = fields.Many2one(related='building_id.project_id', store=True, string='Project')
    subzone_id = fields.Many2one(related='building_id.subzone_id', store=True, string='Subzone')

    description = fields.Text(string='Description')
    layout_image = fields.Image(string='Floor Layout', max_width=2400, max_height=2400)

    unit_ids = fields.One2many('re.unit', 'floor_id', string='Units')
    unit_count = fields.Integer(compute='_compute_counts')
    available_unit_count = fields.Integer(compute='_compute_counts')

    active = fields.Boolean(default=True)

    _unique_code_per_building = models.Constraint(
        'UNIQUE(building_id, code)',
        'Floor code must be unique within a building!',
    )

    @api.depends('unit_ids', 'unit_ids.state')
    def _compute_counts(self):
        for rec in self:
            rec.unit_count = len(rec.unit_ids)
            rec.available_unit_count = len(rec.unit_ids.filtered(lambda u: u.state == 'available'))

    @api.depends('name', 'code', 'building_id.code', 'project_id.code')
    def _compute_display_name(self):
        for rec in self:
            parts = []
            if rec.project_id and rec.project_id.code:
                parts.append(rec.project_id.code)
            if rec.building_id and rec.building_id.code:
                parts.append(rec.building_id.code)
            if rec.code:
                parts.append(rec.code)
            prefix = '/'.join(parts) if parts else ''
            rec.display_name = f'{prefix} - {rec.name}' if prefix else (rec.name or '')

    def action_view_units(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Units', 'res_model': 're.unit',
            'view_mode': 'list,form,kanban',
            'domain': [('floor_id', '=', self.id)],
            'context': {
                'default_floor_id': self.id,
                'default_building_id': self.building_id.id,
                'default_project_id': self.project_id.id,
            },
        }
