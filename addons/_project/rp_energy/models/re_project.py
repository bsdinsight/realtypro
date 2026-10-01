# -*- coding: utf-8 -*-
from odoo import api, fields, models

ENERGY_TYPES = ('wind', 'solar', 'hydro', 'bess')


class ReProject(models.Model):
    _inherit = 're.project'

    # Mở rộng danh sách có sẵn thay vì dựng trường riêng: mọi báo cáo,
    # bộ lọc và "nhóm theo" đang chạy trên project_type vẫn dùng được.
    project_type = fields.Selection(
        selection_add=[
            ('wind', 'Điện gió'),
            ('solar', 'Điện mặt trời'),
            ('hydro', 'Thuỷ điện'),
            ('bess', 'Lưu trữ pin (BESS)'),
        ],
        ondelete={'wind': 'set null', 'solar': 'set null',
                  'hydro': 'set null', 'bess': 'set null'},
    )

    # Lưu lại (store) để view, bộ lọc và báo cáo đều dùng được một chỗ,
    # thay vì mỗi nơi tự viết lại điều kiện project_type in (...).
    is_energy = fields.Boolean(
        string='Dự án năng lượng', compute='_compute_is_energy', store=True,
        help='Bật khi loại dự án là điện gió / điện mặt trời / thuỷ điện / '
             'lưu trữ pin. Dùng để ẩn phần bán bất động sản.')

    capacity_mw = fields.Float(
        string='Công suất (MW)', digits=(10, 2), tracking=True,
        help='Công suất lắp đặt của nhà máy.')
    turbine_count = fields.Integer(
        string='Số tua-bin', tracking=True,
        help='Số tổ máy / tua-bin của dự án điện gió.')
    date_grid_connection = fields.Date(
        string='Ngày đóng điện', tracking=True,
        help='Ngày hoà lưới lần đầu (first energisation).')
    date_cod = fields.Date(
        string='Ngày vận hành thương mại (COD)', tracking=True,
        help='Mốc cam kết trong hợp đồng mua bán điện. Trượt ngày này '
             'thường kéo theo phạt, nên nó là mốc chịu lực của cả tiến độ.')
    ppa_partner_id = fields.Many2one(
        'res.partner', string='Bên mua điện (PPA)', tracking=True)
    ppa_tariff = fields.Float(
        string='Giá điện (/kWh)', digits=(12, 4),
        help='Giá bán điện theo hợp đồng mua bán điện.')

    @api.depends('project_type')
    def _compute_is_energy(self):
        for rec in self:
            rec.is_energy = rec.project_type in ENERGY_TYPES
