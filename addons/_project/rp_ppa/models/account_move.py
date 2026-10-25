# -*- coding: utf-8 -*-
"""Nối hoá đơn kế toán ngược về kỳ sản lượng đã sinh ra nó.

Vì sao cần: app Kinh doanh phải mở được DANH SÁCH hoá đơn tiền điện mà
không bắt người vận hành sang app Kế toán rồi tự lọc. Muốn lọc thì phải
có dấu vết phân biệt hoá đơn tiền điện với mọi hoá đơn bán khác của
công ty — dấu vết ấy đã có sẵn ở `rp.energy.period.line.invoice_id`,
chỉ là chưa nhìn được từ phía hoá đơn.

KHÔNG thêm cờ boolean "là hoá đơn tiền điện". Cờ là bản sao của sự
thật, mà bản sao thì sẽ lệch: xoá dòng phân bổ đi mà cờ vẫn bật là hoá
đơn nằm lại trong danh sách mãi mãi. Quan hệ ngược không lệch được.
"""
from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    energy_line_ids = fields.One2many(
        'rp.energy.period.line', 'invoice_id',
        string='Dòng sản lượng đã tính tiền')
    energy_period_ids = fields.Many2many(
        'rp.energy.period', string='Kỳ sản lượng',
        compute='_compute_energy', store=True)
    energy_project_id = fields.Many2one(
        're.project', string='Dự án điện',
        compute='_compute_energy', store=True, index=True,
        help='Suy từ dòng sản lượng. Một hoá đơn gộp nhiều kỳ thì các kỳ '
             'ấy đều của cùng một dự án và cùng một bên mua.')
    energy_mwh = fields.Float(
        string='Sản lượng (MWh)', digits=(16, 3),
        compute='_compute_energy', store=True)

    @api.depends('energy_line_ids', 'energy_line_ids.period_id',
                 'energy_line_ids.energy_mwh')
    def _compute_energy(self):
        for mv in self:
            ky = mv.energy_line_ids.mapped('period_id')
            mv.energy_period_ids = [(6, 0, ky.ids)]
            mv.energy_project_id = ky.mapped('project_id')[:1]
            mv.energy_mwh = sum(mv.energy_line_ids.mapped('energy_mwh'))
