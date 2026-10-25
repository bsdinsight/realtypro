# -*- coding: utf-8 -*-
"""Kho thuộc nhà máy nào — và vì sao trường này ĐƯỢC PHÉP TRỐNG.

Người vận hành hỏi "nhà máy này đang có gì trong tay", nhưng tồn kho
thì ghi theo KHO. Trước đây hai câu ấy chỉ nối với nhau bằng cái TÊN:
đặt kho là "Kho hiện trường <tên nhà máy>" thì người đọc tự hiểu. Máy
không đọc được tên, nên không lọc, không cộng, không cảnh báo theo nhà
máy được.

**Để trống là có nghĩa, không phải là thiếu dữ liệu.** Kho trung tâm
giữ phụ tùng lớn dùng CHUNG cho cả đội máy — một hộp số dự phòng cho
bốn mươi hai tua-bin, chứ không phải mỗi nhà máy sắm một con. Đó chính
là lý do kinh tế của việc gom kho, và là khoản tiền lớn nhất nằm trong
kho phụ tùng điện gió. Ép mỗi kho phải thuộc một nhà máy là xoá mất
khái niệm ấy.

Vì vậy đọc trường này theo hai nước:
  có nhà máy  → kho hiện trường, hàng nằm tại chỗ của nhà máy ấy
  để trống    → kho dùng chung, mọi nhà máy đều với tới được
"""
from odoo import fields, models


class StockWarehouse(models.Model):
    _inherit = 'stock.warehouse'

    eam_plant_id = fields.Many2one(
        'eam.location', string='Nhà máy',
        domain="[('location_type', '=', 'plant')]", index=True,
        help='Kho hiện trường thì chọn nhà máy. ĐỂ TRỐNG nghĩa là kho '
             'dùng chung cho mọi nhà máy — đó là trường hợp của kho '
             'trung tâm, nơi giữ phụ tùng lớn luân chuyển giữa các nhà '
             'máy. Để trống không phải là khai thiếu.')
