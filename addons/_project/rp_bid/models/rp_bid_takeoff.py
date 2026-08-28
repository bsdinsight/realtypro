# -*- coding: utf-8 -*-
"""rp.bid.takeoff — Dòng bóc tách khối lượng của một dòng BoQ.

Đây là tầng mà mọi phần mềm dự toán Việt Nam đều có và mọi ERP đều
thiếu: khối lượng không phải một con số, nó là một PHÉP TÍNH có diễn
giải.

    Bê tông cọc D1500 ── 4.477,31570 m³
       ├ Cọc đại trà Ca      29 × 0,75 × 0,75 × 47,3 × 3,1415 = 2.424
       ├ Cọc đại trà Cb      25 × 0,75 × 0,75 × 46,9 × 3,1415 = 2.072
       ├ Trừ ống thép D60   −58 × 0,03 × 0,03 × 47,2 × 3,1415 =    −7,74
       └ Trừ con kê bê tông                                   =    −2,64

Hai điểm quyết định:

* **Cho phép ÂM.** Dòng trừ (trừ thể tích ống siêu âm, trừ con kê) là
  nghiệp vụ bình thường, không phải dữ liệu hỏng. Chặn số âm ở đây sẽ
  ép người dùng tự trừ ngoài giấy rồi gõ kết quả vào — mất sạch dấu vết.
* **`factor` (hệ số) tách riêng.** Đó là chỗ để π, hệ số hao hụt, hệ số
  chuyển đổi đơn vị. Nhân sẵn vào kích thước sẽ không ai đọc lại được vì
  sao ra con số đó.
"""
from odoo import api, fields, models


class RpBidTakeoff(models.Model):
    _name = 'rp.bid.takeoff'
    _description = 'Dòng bóc tách khối lượng'
    _order = 'line_id, sequence, id'

    line_id = fields.Many2one(
        'rp.bid.boq.line', string='Dòng BoQ',
        required=True, ondelete='cascade', index=True)
    # Hạng mục lấy ăn theo dòng BoQ mẹ. Cần store vì khi nhìn từ CẤU KIỆN,
    # các dòng bóc tách đến từ nhiều dòng BoQ nằm ở những hạng mục khác
    # nhau — không có cột này thì không biết dòng nào thuộc đâu, mà cũng
    # không lọc hay nhóm theo hạng mục được.
    bid_structure_id = fields.Many2one(
        related='line_id.bid_structure_id', string='Hạng mục',
        store=True, index=True)
    # Dự án / Gói thầu chỉ để LỌC ở màn hình phẳng. Store vì Odoo không
    # cho domain trên trường không có cột.
    project_id = fields.Many2one(
        related='line_id.project_id', string='Dự án', store=True, index=True)
    package_id = fields.Many2one(
        related='line_id.package_id', string='Gói thầu',
        store=True, index=True)
    norm_code = fields.Char(
        related='line_id.norm_code', string='Mã định mức', store=True)
    uom_id = fields.Many2one(
        related='line_id.uom_id', string='ĐVT')
    sequence = fields.Integer(default=10)
    name = fields.Char(
        string='Diễn giải', required=True,
        help='VD "Cọc đại trà Ca", "Trừ thể tích ống siêu âm D60".')

    count = fields.Float(
        string='Số bộ phận', digits=(16, 3), default=1.0,
        help='Số cấu kiện giống nhau. Để ÂM khi đây là dòng trừ.')
    length = fields.Float(string='Dài', digits=(16, 5))
    width = fields.Float(string='Rộng', digits=(16, 5))
    height = fields.Float(string='Cao / Sâu', digits=(16, 5))
    factor = fields.Float(
        string='Hệ số', digits=(16, 7), default=1.0,
        help='Hệ số nhân thêm: π cho tiết diện tròn, hệ số hao hụt, hệ số '
             'quy đổi đơn vị…')

    quantity = fields.Float(
        string='Khối lượng', digits=(16, 5),
        compute='_compute_quantity', store=True, readonly=False,
        help='Tự tính = số bộ phận × dài × rộng × cao × hệ số. Kích thước '
             'nào bỏ trống thì bỏ qua chiều đó, nên nhập được cả khối '
             'lượng theo mét dài hay theo cái.')

    note = fields.Char(string='Ghi chú')

    @api.depends('count', 'length', 'width', 'height', 'factor')
    def _compute_quantity(self):
        for rec in self:
            qty = rec.count if rec.count else 0.0
            # Bỏ qua chiều để trống thay vì nhân với 0: một dòng "192 md
            # tường dẫn" chỉ có chiều dài, nhân với rộng=0 sẽ ra 0.
            for dim in (rec.length, rec.width, rec.height):
                if dim:
                    qty *= dim
            rec.quantity = qty * (rec.factor if rec.factor else 1.0)
