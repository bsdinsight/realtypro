# -*- coding: utf-8 -*-
"""Vị trí kho — đánh dấu nơi hàng KHÔNG được coi là dùng được.

Luật nghiệp vụ: *hàng cách ly, hỏng hoặc chờ kiểm tra không tính vào tồn
khả dụng*. Odoo không có khái niệm đó sẵn — mọi vị trí ``internal`` đều
cộng vào ``qty_available``. Nên một con hộp số vừa tháo khỏi máy, chưa ai
kiểm, vẫn làm tồn kho trông như đủ hàng.

Cách làm ở đây là gắn cờ lên chính vị trí, rồi **chặn ở cửa xuất**: không
cho chọn vị trí đó làm kho xuất. Đó là chỗ duy nhất con số này thật sự
quyết định điều gì — ai đó có mở báo cáo tổng công ty ra thì vẫn thấy
hàng, nhưng không ai lấy nó ra lắp lên máy được.

Chọn cách này thay vì bịa một trường "trạng thái hàng" riêng, vì trạng
thái rời khỏi vị trí là hai sổ: hàng nằm ở kệ A mà trạng thái ghi "đã
thanh lý" thì không ai biết tin cái nào.
"""
from odoo import fields, models


class StockLocation(models.Model):
    _inherit = 'stock.location'

    eam_cam_xuat = fields.Boolean(
        string='Không dùng được cho bảo trì',
        help='Hàng nằm ở đây chưa đủ điều kiện lắp lên máy: chờ kiểm tra, '
             'cách ly, hỏng, hoặc đang gửi đi sửa. Vị trí này sẽ không '
             'chọn được làm kho xuất.')
