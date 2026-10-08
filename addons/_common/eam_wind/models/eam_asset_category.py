# -*- coding: utf-8 -*-
from odoo import fields, models


class EamAssetCategory(models.Model):
    """Thêm các trường riêng của ngành điện gió vào cây loại cấu phần.

    Đây là ví dụ mẫu của kỷ luật ba lớp: lõi không biết "hộp số" hay
    "truyền động trực tiếp" là gì; gói ngành mới biết. Trường nào chỉ có
    nghĩa trong một ngành thì nằm ở gói ngành đó, không nhét vào lõi.
    """
    _inherit = 'eam.asset.category'

    platform_scope = fields.Selection(
        [('all', 'Mọi nền tảng'),
         ('geared', 'Chỉ máy có hộp số'),
         ('direct', 'Chỉ máy truyền động trực tiếp')],
        string='Áp dụng cho nền tảng', default='all',
        help='Máy truyền động trực tiếp KHÔNG có hộp số. Cứng hoá hộp số '
             'vào mọi tua-bin là sai ngay từ dòng đầu.')
    rdspp_code = fields.Char(
        string='Mã RDS-PP',
        help='Để trống. RDS-PP là tài sản có bản quyền của VGB nên không '
             'ship theo sản phẩm; khách có giấy phép thì tự điền. Ánh xạ '
             'một chiều: ReliaWind quy về RDS-PP được, ngược lại không.')
    rank_failure = fields.Integer(
        string='Hạng theo SỐ LẦN hỏng',
        help='Giá trị THAM CHIẾU từ tổng hợp 18 cơ sở dữ liệu công khai '
             '(>18.000 tua-bin). Chỉ để gợi ý mức quan trọng ban đầu.')
    rank_downtime = fields.Integer(
        string='Hạng theo THỜI GIAN dừng',
        help='Hai trục xếp hạng KHÁC NHAU: cụm hỏng nhiều nhất không phải '
             'cụm gây dừng lâu nhất. Nguyên nhân là độ phức tạp của việc '
             'sửa, không phải tần suất hỏng.')
    reference_note = fields.Text(string='Ghi chú tham chiếu')
