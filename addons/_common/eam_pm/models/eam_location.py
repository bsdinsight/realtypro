# -*- coding: utf-8 -*-
from odoo import _, fields, models


class EamLocation(models.Model):
    """Đồng hồ và lịch bảo trì gộp về vị trí, và bơm lên bản đồ."""
    _inherit = 'eam.location'

    meter_ids = fields.One2many('eam.meter', 'location_id', string='Đồng hồ')
    pm_schedule_ids = fields.One2many(
        'eam.pm.schedule', 'location_id', string='Lịch bảo trì')

    def _map_payload_one(self, tu, den):
        d = super()._map_payload_one(tu, den)
        ls = self.pm_schedule_ids.filtered('active')
        if not ls:
            return d
        qua = ls.filtered(lambda s: s.state == 'overdue')
        sap = ls.filtered(lambda s: s.state == 'due_soon')
        dong = []
        if qua:
            dong.append({'label': 'Bảo trì QUÁ HẠN', 'warn': True,
                         'value': '%d kế hoạch — %s'
                                  % (len(qua), qua[0].plan_id.name)})
        elif sap:
            dong.append({'label': 'Bảo trì sắp tới hạn',
                         'value': '%s (còn %d ngày)'
                                  % (sap[0].plan_id.name,
                                     sap[0].days_to_due)})
        gio = self.meter_ids.filtered(
            lambda m: m.meter_type == 'operating_hours')[:1]
        if gio and gio.current_value:
            dong.append({'label': 'Giờ máy chạy',
                         'value': '{:,.0f} giờ'.format(gio.current_value)})
        if dong:
            d.setdefault('extra', []).extend(dong)
        return d

    def action_mo_lich_bao_tri(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Lịch bảo trì — %s', self.code or ''),
            'res_model': 'eam.pm.schedule',
            'view_mode': 'list,form',
            'domain': [('location_id', '=', self.id)],
        }
