# -*- coding: utf-8 -*-
from odoo import fields, models


class RpTenderPackage(models.Model):
    _inherit = 'rp.tender.package'

    # Dự án điện chia việc theo ba gói lớn, khác hẳn cách chia theo hạng
    # mục của dự án bất động sản. Ghi lại loại gói để báo cáo và màn hình
    # nói đúng ngôn ngữ của chủ đầu tư điện.
    energy_scope = fields.Selection(
        [('hv', 'HV — Trạm nâng áp & đấu nối lưới'),
         ('tsa', 'TSA — Cung cấp tua-bin'),
         ('bop', 'BOP — Hạ tầng & xây lắp phần còn lại'),
         ('om', 'O&M — Vận hành & bảo trì'),
         ('other', 'Khác')],
        string='Loại gói (điện)', tracking=True,
        help='HV: trạm nâng áp, đường dây, đấu nối lưới.\n'
             'TSA: hợp đồng CUNG CẤP thiết bị chính (tua-bin) — tiến độ '
             'theo lô giao hàng và nghiệm thu tại xưởng, không theo khối '
             'lượng thi công.\n'
             'BOP: móng, đường công vụ, bãi lắp dựng, cáp ngầm, nhà điều '
             'hành.\n'
             'O&M: hợp đồng dịch vụ dài hạn sau vận hành.')

    project_is_energy = fields.Boolean(
        related='project_id.is_energy', store=True, string='Dự án năng lượng')
