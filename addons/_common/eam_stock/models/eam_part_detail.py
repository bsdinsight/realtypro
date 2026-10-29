# -*- coding: utf-8 -*-
"""Thông số, tài liệu và mã chéo của phụ tùng.

Ba bảng nhỏ thay vì nhét thêm hai chục cột vào ``product.template``:

* **Thông số** khác nhau theo từng loại. Ổ trục có đường kính trong/ngoài;
  dầu có độ nhớt và tiêu chuẩn; cảm biến có dải đo và tín hiệu ra. Dựng
  cột cố định cho mọi loại thì 90% bản ghi để trống, mà vẫn thiếu đúng
  cái cần.
* **Tài liệu** phải có *phiên bản*. Bản vẽ không có số hiệu bản sửa đổi là
  bản vẽ không dùng được để đặt hàng.
* **Mã chéo** là cách người ta thật sự tìm phụ tùng: cầm con cũ, đọc số
  dập trên vỏ, tra ngược. Số đó thường là mã OEM hoặc mã của một nhà
  phân phối, không phải mã nội bộ của mình.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

LOAI_TAI_LIEU = [
    ('drawing', 'Bản vẽ'),
    ('datasheet', 'Thông số kỹ thuật'),
    ('manual', 'Hướng dẫn lắp đặt / bảo dưỡng'),
    ('cert', 'Chứng chỉ / chứng nhận'),
    ('msds', 'Phiếu an toàn hoá chất (MSDS)'),
    ('other', 'Khác'),
]

LOAI_MA = [
    ('oem', 'Mã OEM (hãng chế tạo thiết bị)'),
    ('mfr', 'Mã nhà sản xuất phụ tùng'),
    ('vendor', 'Mã nhà phân phối'),
    ('old', 'Mã cũ đã thay thế'),
]


class EamPartSpec(models.Model):
    _name = 'eam.part.spec'
    _description = 'Thông số kỹ thuật phụ tùng'
    _order = 'product_tmpl_id, sequence, id'

    product_tmpl_id = fields.Many2one(
        'product.template', string='Phụ tùng', required=True,
        ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    # Cả ba mở dịch, kể cả `value`. Tên thông số và đơn vị thì rõ rồi.
    # Riêng `value` không chỉ vì có giá trị bằng chữ ("Sợi thuỷ tinh +
    # carbon", "Có") — mà vì DẤU PHÂN CÁCH SỐ khác nhau theo ngôn ngữ:
    # "1.800 mm" người đọc tiếng Anh hiểu là 1,8 mm, sai một nghìn lần
    # trên đường kính ổ trục chính. Để một bản chung thì một trong hai
    # phía luôn đọc sai, và đọc sai êm ru chứ không báo lỗi gì.
    name = fields.Char(string='Thông số', required=True, translate=True,
                       help='Ví dụ: Đường kính trong, Độ nhớt, Dải đo')
    value = fields.Char(string='Giá trị', required=True, translate=True)
    uom_label = fields.Char(string='Đơn vị', translate=True)
    is_key = fields.Boolean(
        string='Thông số quyết định',
        help='Thông số mà sai là lắp không vừa hoặc hỏng máy. Hiện ngay '
             'trên danh sách để người xuất kho nhìn thấy trước khi đưa '
             'hàng ra.')

    @api.depends('name', 'value', 'uom_label')
    def _compute_display_name(self):
        for s in self:
            s.display_name = '%s: %s%s' % (
                s.name or '', s.value or '',
                ' %s' % s.uom_label if s.uom_label else '')


class EamPartDoc(models.Model):
    _name = 'eam.part.doc'
    _description = 'Tài liệu phụ tùng'
    _order = 'product_tmpl_id, doc_type, id'

    product_tmpl_id = fields.Many2one(
        'product.template', string='Phụ tùng', required=True,
        ondelete='cascade', index=True)
    name = fields.Char(string='Tên tài liệu', required=True)
    doc_type = fields.Selection(LOAI_TAI_LIEU, string='Loại', required=True,
                                default='drawing')
    revision = fields.Char(
        string='Bản sửa đổi',
        help='Bản vẽ không có số hiệu bản sửa đổi là bản vẽ không dùng '
             'để đặt hàng được — hãng sẽ hỏi lại ngay.')
    doc_date = fields.Date(string='Ngày phát hành')
    attachment_id = fields.Many2one(
        'ir.attachment', string='Tệp đính kèm', ondelete='restrict')
    note = fields.Char(string='Ghi chú')


class EamPartXref(models.Model):
    _name = 'eam.part.xref'
    _description = 'Mã chéo phụ tùng'
    _order = 'product_tmpl_id, code_type, id'

    product_tmpl_id = fields.Many2one(
        'product.template', string='Phụ tùng', required=True,
        ondelete='cascade', index=True)
    code_type = fields.Selection(LOAI_MA, string='Loại mã', required=True,
                                 default='oem')
    code = fields.Char(string='Mã', required=True, index=True)
    partner_id = fields.Many2one(
        'res.partner', string='Của bên nào',
        help='Mã của hãng nào / nhà phân phối nào. Bỏ trống nếu là mã '
             'chung của ngành.')
    note = fields.Char(string='Ghi chú')

    _uniq = models.Constraint(
        'UNIQUE(product_tmpl_id, code_type, code)',
        'Mã chéo này đã khai cho phụ tùng rồi.')

    @api.constrains('code')
    def _check_code(self):
        """Cùng một mã OEM không được trỏ tới hai phụ tùng khác nhau.

        Nếu cho phép, người cầm con cũ tra số dập trên vỏ sẽ nhận hai kết
        quả và không biết chọn cái nào — đúng lúc đang cần quyết nhanh.
        """
        for x in self:
            if x.code_type != 'oem':
                continue
            trung = self.search([
                ('code_type', '=', 'oem'),
                ('code', '=', x.code),
                ('product_tmpl_id', '!=', x.product_tmpl_id.id),
            ], limit=1)
            if trung:
                raise ValidationError(_(
                    'Mã OEM "%(ma)s" đang trỏ tới "%(sp)s". Một mã OEM '
                    'chỉ được trỏ tới một phụ tùng — nếu đúng là hai thứ '
                    'thay thế được cho nhau, khai ở mục Phụ tùng tương '
                    'đương chứ không khai trùng mã.',
                    ma=x.code, sp=trung.product_tmpl_id.display_name))
