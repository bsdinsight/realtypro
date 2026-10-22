# -*- coding: utf-8 -*-
"""Nối sản lượng từ chuỗi điểm đo vào bản ghi hiệu suất ngày.

Ô "Điện năng AC" trên màn hiệu suất trước nay phải nhập tay. Nó chính là
sản lượng tại **bậc công-tơ bán điện** của chuỗi — nên lấy thẳng từ đó.

Vẫn cho sửa tay: nhà máy chưa khai chuỗi thì phải có đường nhập, và có
ngày số công-tơ về muộn nên người ta điền tạm rồi sửa sau.
"""
from odoo import _, api, fields, models


class EamSolarKpi(models.Model):
    _inherit = 'eam.solar.kpi'

    chain_day_id = fields.Many2one(
        'eam.chain.day', string='Lấy từ bậc bán điện', readonly=True,
        help='Dòng sản lượng ngày tại bậc công-tơ bán điện của chuỗi.')

    def action_lay_san_luong_tu_chuoi(self):
        """Điền Điện năng AC từ bậc công-tơ bán điện."""
        D = self.env['eam.chain.day']
        lay = 0
        for rec in self:
            # Ưu tiên bậc khai riêng cho tỷ số hiệu suất. KHÔNG tự
            # rơi về bậc bán điện: hai mốc đó lệch nhau vài phần trăm,
            # và lấy nhầm thì PR sai mà nhìn vẫn hợp lý.
            d = D.search([('plant_id', '=', rec.plant_id.id),
                          ('date', '=', rec.date),
                          ('node_id.is_pr_source', '=', True)], limit=1)
            if d:
                rec.energy_ac = d.energy
                rec.chain_day_id = d.id
                lay += 1
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success' if lay else 'warning',
                'title': _('Đã lấy %s dòng', lay),
                'message': _('Dòng không lấy được là do chuỗi chưa đánh '
                             'dấu bậc "Tử số tỷ số hiệu suất". Cố ý không '
                             'tự lấy bậc bán điện thay thế — hai mốc đó '
                             'lệch nhau vài phần trăm.'),
                'sticky': False,
            },
        }
