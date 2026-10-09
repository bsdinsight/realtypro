# -*- coding: utf-8 -*-
from odoo import _, api, fields, models


class ReProject(models.Model):
    """Lối vào bàn giao từ chính dự án."""
    _inherit = 're.project'

    handover_ids = fields.One2many(
        'rp.handover', 'project_id', string='Biên bản bàn giao')
    handover_count = fields.Integer(
        string='Số biên bản', compute='_compute_handover')
    handover_done = fields.Integer(
        string='Vị trí đã bàn giao', compute='_compute_handover')
    handover_ready = fields.Integer(
        string='Vị trí sẵn sàng bàn giao', compute='_compute_handover',
        help='Đã qua cổng nghiệm thu trong sổ dựng máy mà chưa có trong '
             'biên bản bàn giao nào. Đây là việc đang tồn đọng — mỗi trụ '
             'chưa bàn giao là một đồng hồ bảo hành chưa ai bấm bắt đầu.')

    @api.depends('handover_ids.state', 'plant_location_id')
    def _compute_handover(self):
        S = self.env['rp.erection.step']
        G = self.env['rp.erection.gate']
        toc = G.search([('code', '=', 'G9-TOC')], limit=1)
        for p in self:
            p.handover_count = len(p.handover_ids)
            da = p.handover_ids.mapped('line_ids').filtered(
                lambda l: l.state == 'done')
            p.handover_done = len(da)
            san = 0
            if p.plant_location_id and toc:
                xong = S.search([
                    ('gate_id', '=', toc.id), ('state', '=', 'done'),
                    ('location_id', 'child_of', p.plant_location_id.id)])
                san = len(xong.mapped('location_id') - da.mapped('location_id'))
            p.handover_ready = san

    def action_mo_ban_giao(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Bàn giao sang vận hành — %s', self.name or ''),
            'res_model': 'rp.handover',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id,
                        'default_plant_id': self.plant_location_id.id},
        }
