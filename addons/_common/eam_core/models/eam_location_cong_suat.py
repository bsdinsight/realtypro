# -*- coding: utf-8 -*-
"""Công suất đặt của một vị trí — thuộc tính NỀN, không thuộc bản đồ.

Trường này trước nằm trong gói bản đồ, vì bản đồ là nơi đầu tiên cần
tới nó. Nhưng công suất đặt là **đặc tính của chính vị trí**: bảng hiệu
suất tổ máy cần nó để ra hệ số công suất, phần sản lượng theo kỳ cần nó
để ra công suất đặt toàn nhà máy, và cả hai đều chạy được khi không có
bản đồ.

Để nó ở gói bản đồ tạo ra một vòng phụ thuộc: bản đồ cần bảng tổ máy để
tô màu theo hiệu suất, mà bảng tổ máy lại cần bản đồ để biết công suất
đặt. Odoo không giải được vòng ấy và bỏ cả chuỗi module ở trạng thái dở
dang — triệu chứng là "some modules have inconsistent states", còn màn
hình thì vẫn mở được nên không ai nghi.
"""
from odoo import fields, models


class EamLocation(models.Model):
    _inherit = 'eam.location'

    rated_power_mw = fields.Float(
        string='Công suất đặt (MW)', digits=(8, 3),
        help='Công suất định mức của tổ máy đặt tại vị trí này. Dùng để '
             'tính hệ số công suất — chưa khai thì hệ KHÔNG đoán, vì '
             'chia cho một con số đoán bừa ra tỷ lệ trông hợp lý và sai.')
