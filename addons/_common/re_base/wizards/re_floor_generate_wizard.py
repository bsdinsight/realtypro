import logging
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class ReFloorGenerateWizard(models.TransientModel):
    _name = 're.floor.generate.wizard'
    _description = 'Generate Floors Wizard'

    building_id = fields.Many2one('re.building', string='Building', required=True)
    project_id = fields.Many2one(related='building_id.project_id', string='Project')

    mode = fields.Selection(
        [('simple', 'Simple - Sequential floors (1, 2, 3...)'),
         ('skip', 'Skip floors (e.g., skip 13, 14)'),
         ('custom', 'Custom pattern (B2, B1, GF, M, 1-30...)')],
        string='Mode', default='simple', required=True,
    )

    floor_from = fields.Integer(string='From Floor', default=1)
    floor_to = fields.Integer(string='To Floor', default=10)
    skip_floors_text = fields.Char(string='Skip Floor Numbers', default='13, 14')
    custom_pattern = fields.Text(
        string='Custom Pattern',
        default='-1|B1|Basement 1\n0|GF|Ground Floor\n1|01|Floor 1\n2|02|Floor 2',
    )

    code_pattern = fields.Char(string='Code Pattern', default='{n:02d}', required=True)
    name_pattern = fields.Char(string='Name Pattern', default='Floor {n}', required=True)

    conflict_strategy = fields.Selection(
        [('skip', 'Skip existing floors (only create new)'),
         ('update', 'Update existing floors'),
         ('replace', 'Replace ALL ⚠️')],
        string='If floor already exists', default='skip', required=True,
    )

    preview_text = fields.Text(string='Preview', compute='_compute_preview', readonly=True)

    state = fields.Selection([('draft', 'Draft'), ('done', 'Done')], default='draft')
    log_text = fields.Text(string='Log', readonly=True)
    created_count = fields.Integer(readonly=True)
    updated_count = fields.Integer(readonly=True)
    skipped_count = fields.Integer(readonly=True)
    deleted_count = fields.Integer(readonly=True)

    @api.constrains('floor_from', 'floor_to', 'mode')
    def _check_floor_range(self):
        for rec in self:
            if rec.mode in ('simple', 'skip'):
                if rec.floor_from > rec.floor_to:
                    raise ValidationError(_('From Floor must be ≤ To Floor.'))
                if rec.floor_to - rec.floor_from > 200:
                    raise ValidationError(_('Cannot generate more than 200 floors at once.'))

    @api.depends('mode', 'floor_from', 'floor_to', 'skip_floors_text',
                 'custom_pattern', 'code_pattern', 'name_pattern')
    def _compute_preview(self):
        for rec in self:
            try:
                floors = rec._build_floor_list()
                if not floors:
                    rec.preview_text = '(no floors to generate)'
                    continue
                lines = [f'  #{f["floor_number"]:>3}  code={f["code"]:<8}  name={f["name"]}'
                         for f in floors[:50]]
                if len(floors) > 50:
                    lines.append(f'  ... and {len(floors) - 50} more')
                rec.preview_text = f'Will generate {len(floors)} floor(s):\n\n' + '\n'.join(lines)
            except Exception as e:
                rec.preview_text = f'⚠ Error: {e}'

    def _build_floor_list(self):
        self.ensure_one()
        floors = []
        if self.mode == 'simple':
            for n in range(self.floor_from, self.floor_to + 1):
                floors.append(self._make_floor_dict(n))
        elif self.mode == 'skip':
            skip_set = self._parse_skip_floors()
            for n in range(self.floor_from, self.floor_to + 1):
                if n not in skip_set:
                    floors.append(self._make_floor_dict(n))
        elif self.mode == 'custom':
            for line_idx, line in enumerate((self.custom_pattern or '').splitlines(), start=1):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                parts = line.split('|')
                if len(parts) != 3:
                    raise UserError(_(
                        'Line %(idx)s invalid: "%(line)s"\nExpected format: NUMBER|CODE|NAME',
                        idx=line_idx, line=line,
                    ))
                try:
                    floor_number = int(parts[0].strip())
                except ValueError:
                    raise UserError(_(
                        'Line %(idx)s: floor number must be integer, got "%(val)s"',
                        idx=line_idx, val=parts[0],
                    ))
                code = parts[1].strip()
                name = parts[2].strip()
                if not code or not name:
                    raise UserError(_('Line %(idx)s: code and name cannot be empty', idx=line_idx))
                floors.append({'floor_number': floor_number, 'code': code, 'name': name})
        return floors

    def _make_floor_dict(self, n):
        try:
            code = self.code_pattern.format(n=n)
        except (KeyError, ValueError, IndexError) as e:
            raise UserError(_('Invalid code pattern "%(p)s": %(err)s', p=self.code_pattern, err=e))
        try:
            name = self.name_pattern.format(n=n)
        except (KeyError, ValueError, IndexError) as e:
            raise UserError(_('Invalid name pattern "%(p)s": %(err)s', p=self.name_pattern, err=e))
        return {'floor_number': n, 'code': code, 'name': name}

    def _parse_skip_floors(self):
        if not self.skip_floors_text:
            return set()
        skip = set()
        for token in re.split(r'[,\s]+', self.skip_floors_text.strip()):
            if not token:
                continue
            try:
                skip.add(int(token))
            except ValueError:
                raise UserError(_('Skip floors: cannot parse "%s" as integer') % token)
        return skip

    def action_generate(self):
        self.ensure_one()
        floors_to_create = self._build_floor_list()
        if not floors_to_create:
            raise UserError(_('No floors to generate.'))

        Floor = self.env['re.floor']
        building = self.building_id
        existing = {f.code: f for f in building.floor_ids}

        created = updated = skipped = deleted = 0
        log_lines = []

        if self.conflict_strategy == 'replace':
            floors_with_units = building.floor_ids.filtered(lambda f: f.unit_count > 0)
            if floors_with_units:
                raise UserError(_(
                    'Cannot replace: %(n)s floor(s) have units linked.\n%(codes)s',
                    n=len(floors_with_units),
                    codes=', '.join(f.code for f in floors_with_units),
                ))
            deleted = len(building.floor_ids)
            building.floor_ids.unlink()
            log_lines.append(f'Deleted {deleted} existing floor(s)')
            existing = {}

        for floor_data in floors_to_create:
            code = floor_data['code']
            vals = {
                'building_id': building.id,
                'code': code,
                'name': floor_data['name'],
                'floor_number': floor_data['floor_number'],
            }
            if code in existing:
                if self.conflict_strategy == 'skip':
                    skipped += 1
                    log_lines.append(f'SKIP {code} (already exists)')
                elif self.conflict_strategy == 'update':
                    existing[code].write({
                        'name': floor_data['name'],
                        'floor_number': floor_data['floor_number'],
                    })
                    updated += 1
                    log_lines.append(f'UPDATE {code}')
            else:
                Floor.create(vals)
                created += 1
                log_lines.append(f'CREATE {code} ({floor_data["name"]})')

        self.write({
            'state': 'done',
            'created_count': created,
            'updated_count': updated,
            'skipped_count': skipped,
            'deleted_count': deleted,
            'log_text': '\n'.join(log_lines),
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 're.floor.generate.wizard',
            'res_id': self.id,
            'view_mode': 'form', 'target': 'new',
        }

    def action_view_floors(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Floors'), 'res_model': 're.floor',
            'view_mode': 'list,form',
            'domain': [('building_id', '=', self.building_id.id)],
            'context': {
                'default_building_id': self.building_id.id,
                'default_project_id': self.project_id.id,
            },
        }
