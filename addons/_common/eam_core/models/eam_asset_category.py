# -*- coding: utf-8 -*-
from odoo import api, fields, models


class EamAssetCategory(models.Model):
    """Loại cấu phần — cây phân loại thiết bị, dùng để ghi nhận hỏng hóc.

    Lõi chỉ dựng CÂY RỖNG. Nội dung — 11 phân hệ, 19 cụm của một tua-bin
    gió chẳng hạn — do gói ngành nạp vào. Lõi mà biết chữ "hộp số" là lõi
    đã hết trung lập.

    Cột ``alias_names`` không phải trang trí. Cùng một cụm mang tên khác
    nhau tuỳ nguồn: *Converter* / *Frequency converter*; *Gearbox* /
    *System for converting speed*; *Blades* / *Rotor blades*. Nhập dữ
    liệu từ hai OEM khác nhau mà không có cột này là đẻ ra hai loại trùng
    nghĩa, và mọi thống kê về sau cộng nhầm.
    """
    _name = 'eam.asset.category'
    _description = 'Loại cấu phần'
    _parent_name = 'parent_id'
    _parent_store = True
    _order = 'complete_name'

    name = fields.Char(string='Tên loại', required=True, translate=True)
    code = fields.Char(string='Mã', index=True)
    complete_name = fields.Char(
        string='Tên đầy đủ', compute='_compute_complete_name', store=True,
        recursive=True)
    parent_id = fields.Many2one(
        'eam.asset.category', string='Thuộc loại', ondelete='restrict',
        index=True)
    child_ids = fields.One2many(
        'eam.asset.category', 'parent_id', string='Loại con')
    parent_path = fields.Char(index=True)
    level = fields.Integer(
        string='Cấp', compute='_compute_complete_name', store=True,
        recursive=True)

    alias_names = fields.Char(
        string='Tên gọi khác',
        help='Các tên khác của cùng loại này, ngăn bằng dấu phẩy. Dùng '
             'khi nhập dữ liệu từ nguồn của OEM hay nhà thầu dùng từ '
             'khác — tránh đẻ ra hai loại trùng nghĩa.')
    is_rotable_default = fields.Boolean(
        string='Mặc định là vật tư quay vòng',
        help='Cấu phần tháo ra đem đi đại tu rồi lắp lại, giữ nguyên lịch '
             'sử theo sê-ri. Giá trị gợi ý khi tạo tài sản mới.')
    is_equipment = fields.Boolean(
        string='Là thiết bị',
        help='Bật khi loại này là một THIẾT BỊ — thứ có lý lịch riêng, '
             'có lệnh công việc, có phụ tùng, và đáng đứng một dòng '
             'trong sổ thiết bị. Tắt khi nó là CẤU PHẦN nằm bên trong '
             'một thiết bị khác.\n\n'
             'Cờ này quyết định cột "Cấp tài sản" của mọi tài sản thuộc '
             'loại, và quyết định tài sản ấy có hiện khi mở sổ Tài sản '
             'hay không. Đây là quyết định NGHIỆP VỤ nên để ở đây cho '
             'người dùng tự đổi, không suy từ dữ liệu.\n\n'
             'Trước đây máy tự suy: tài sản nào không lắp trong tài sản '
             'nào thì là thiết bị. Suy vậy là sai — hộp gom chuỗi lắp '
             'trong dàn pin, bộ biến tần tua-bin lắp trong cụm điện, cả '
             'hai đều là thiết bị thật mà bị xem là cấu phần rồi biến '
             'mất khỏi sổ.')
    is_catch_all = fields.Boolean(
        string='Rổ "Khác"',
        help='Mỗi cây phân loại phải có một rổ Khác. Không có thì người '
             'nhập sẽ nhét bừa vào loại gần nhất và làm hỏng thống kê.')
    note = fields.Text(string='Ghi chú')
    active = fields.Boolean(default=True)
    asset_count = fields.Integer(
        string='Số tài sản', compute='_compute_asset_count')

    _uniq_code = models.Constraint(
        'UNIQUE(code)', 'Mã loại cấu phần không được trùng.')

    @api.depends('name', 'parent_id.complete_name', 'parent_id.level')
    def _compute_complete_name(self):
        for c in self:
            c.complete_name = ('%s / %s' % (c.parent_id.complete_name, c.name)
                               if c.parent_id else c.name)
            c.level = (c.parent_id.level or 0) + 1 if c.parent_id else 1

    def _compute_asset_count(self):
        # Đếm cả loại con: hỏi "máy phát hỏng mấy lần" thì phải gộp mọi
        # loại nằm dưới nó.
        A = self.env['eam.asset']
        for c in self:
            c.asset_count = A.search_count([('category_id', 'child_of', c.id)])
