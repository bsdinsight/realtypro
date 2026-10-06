# -*- coding: utf-8 -*-
"""Cộng doanh thu bán điện lên dự án."""
from odoo import api, fields, models


class ReProject(models.Model):
    _inherit = 're.project'

    ppa_ids = fields.One2many('rp.ppa', 'project_id', string='Hợp đồng bán điện')
    ppa_count = fields.Integer(compute='_compute_ban_dien')
    energy_period_ids = fields.One2many(
        'rp.energy.period', 'project_id', string='Kỳ sản lượng')
    energy_period_count = fields.Integer(compute='_compute_ban_dien')
    energy_net_total = fields.Float(
        string='Sản lượng giao nhận luỹ kế (MWh)', digits=(16, 3),
        compute='_compute_ban_dien')
    energy_curtailed_total = fields.Float(
        string='Bị cắt giảm luỹ kế (MWh)', digits=(16, 3),
        compute='_compute_ban_dien')
    energy_revenue_total = fields.Monetary(
        string='Doanh thu bán điện luỹ kế', compute='_compute_ban_dien',
        currency_field='currency_id')
    energy_shortfall_total = fields.Float(
        string='Hụt do khả dụng luỹ kế (MWh)', digits=(16, 3),
        compute='_compute_ban_dien',
        help='Khoản đòi NHÀ THẦU theo cam kết khả dụng, không phải doanh '
             'thu bán điện.')

    @api.depends('energy_period_ids.revenue_total',
                 'energy_period_ids.net_mwh', 'ppa_ids')
    def _compute_ban_dien(self):
        for p in self:
            ky = p.energy_period_ids.filtered(
                lambda k: k.state in ('confirmed', 'invoiced'))
            p.ppa_count = len(p.ppa_ids)
            p.energy_period_count = len(p.energy_period_ids)
            p.energy_net_total = sum(ky.mapped('net_mwh'))
            p.energy_curtailed_total = sum(ky.mapped('curtailed_mwh'))
            p.energy_revenue_total = sum(ky.mapped('revenue_total'))
            p.energy_shortfall_total = sum(ky.mapped('shortfall_mwh'))

    def action_mo_ppa(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': 'Hợp đồng bán điện',
            'res_model': 'rp.ppa', 'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }

    def action_mo_san_luong(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': 'Sản lượng theo kỳ',
            'res_model': 'rp.energy.period', 'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }
