# -*- coding: utf-8 -*-
"""Giai đoạn (Phase) của dự án năng lượng.

`re.subzone` dựng cho bất động sản: phân khu có toà nhà, có căn hộ, có
loại "Apartment Block / Villa Zone", có ngày bàn giao và cờ mở bán. Nhà
máy điện dùng CÙNG bảng đó nhưng nghĩa khác hẳn — một giai đoạn đầu tư
có công suất, số tua-bin, ngày đóng điện và ngày vận hành thương mại.

Không dựng bảng mới: giai đoạn vẫn là một lát cắt của dự án, vẫn gắn
hợp đồng và lịch như phân khu. Chỉ thêm các ô của ngành và giấu các ô
của nhà ở — giấu theo DỰ ÁN (`is_energy`) chứ không theo cờ triển khai,
vì một bản triển khai có thể có cả dự án điện lẫn dự án bất động sản,
và lúc đó mỗi bản ghi phải tự quyết định.
"""
from odoo import fields, models


class ReSubzone(models.Model):
    _inherit = 're.subzone'

    # Dùng cho điều kiện ẩn/hiện trên form. Phải là trường THẬT trong
    # view thì modifier mới đọc được — không viết thẳng
    # `project_id.is_energy` vào `invisible` được.
    is_energy = fields.Boolean(
        related='project_id.is_energy', readonly=True,
        string='Thuộc dự án năng lượng')

    capacity_mw = fields.Float(
        string='Công suất lắp đặt (MW)', digits=(10, 2),
        help='Công suất của riêng giai đoạn này, không phải cả dự án.')
    turbine_count = fields.Integer(
        string='Số tua-bin',
        help='Số tua-bin thuộc giai đoạn này.')
    date_grid_connection = fields.Date(
        string='Ngày đóng điện',
        help='Ngày hoà lưới lần đầu. Khác ngày COD: đóng điện xong vẫn '
             'còn chạy thử và nghiệm thu trước khi được công nhận vận '
             'hành thương mại.')
    date_cod = fields.Date(
        string='Ngày vận hành thương mại (COD)',
        help='Mốc tính doanh thu bán điện và là đích của đường găng. '
             'Trễ COD thường kéo theo phạt trong hợp đồng mua bán điện.')
