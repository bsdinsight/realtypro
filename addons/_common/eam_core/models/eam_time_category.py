# -*- coding: utf-8 -*-
from odoo import api, fields, models


class EamTimeCategory(models.Model):
    """Loại thời gian — mỗi giờ của một thiết bị thuộc về đúng một loại.

    Lõi chỉ dựng cây rỗng và cơ chế; nội dung do gói ngành nạp. Với điện
    gió, nội dung là phân loại trạng thái của IEC 61400-26-1:2019.

    Ba thứ làm bảng này khác một bảng mã phẳng
    ------------------------------------------

    **① ``counts_as_downtime`` không suy ra được từ tên.** Cắt giảm công
    suất do ràng buộc lưới được xếp là ĐANG HOẠT ĐỘNG — phát một phần,
    giảm tải — **không phải thời gian dừng**. Ai nghe "bị cắt giảm" cũng
    tưởng là dừng, nên phải khai tường minh trên từng loại.

    **② ``priority`` để phân xử khi nhiều loại xảy ra đồng thời.** Một
    máy đang hỏng thì bị cắt giảm: giờ đó tính vào đâu? Chuẩn giải bằng
    thứ tự ưu tiên, không bằng cảm tính của người nhập.

    **③ "Thông tin không khả dụng" là MỘT LOẠI THỜI GIAN**, không phải
    lỗi dữ liệu. Mất kết nối SCADA phải được hạch toán, không được bỏ
    qua và càng không được mặc định là máy chạy tốt.
    """
    _name = 'eam.time.category'
    _description = 'Loại thời gian'
    _parent_name = 'parent_id'
    _parent_store = True
    _order = 'priority, code'

    name = fields.Char(string='Tên loại', required=True, translate=True)
    code = fields.Char(string='Mã', required=True, index=True)
    complete_name = fields.Char(
        string='Tên đầy đủ', compute='_compute_complete', store=True,
        recursive=True)
    parent_id = fields.Many2one(
        'eam.time.category', string='Thuộc loại', ondelete='restrict',
        index=True)
    child_ids = fields.One2many(
        'eam.time.category', 'parent_id', string='Loại con')
    parent_path = fields.Char(index=True)
    level = fields.Integer(
        string='Cấp', compute='_compute_complete', store=True, recursive=True)

    # Số nhỏ thắng. Dùng khi hai loại cùng xảy ra trên một thiết bị —
    # ví dụ đang hỏng thì bị cắt giảm.
    priority = fields.Integer(
        string='Thứ tự ưu tiên', default=100, required=True,
        help='Số NHỎ thắng. Khi hai loại xảy ra đồng thời trên cùng một '
             'thiết bị, giờ đó tính vào loại có số nhỏ hơn.')
    counts_as_downtime = fields.Boolean(
        string='Tính là thời gian dừng',
        help='KHÔNG suy ra được từ tên. Cắt giảm do ràng buộc lưới được '
             'xếp là ĐANG HOẠT ĐỘNG (phát một phần, giảm tải) — không '
             'phải dừng máy. Khai sai ô này là sai toàn bộ khả dụng.')
    is_mandatory = fields.Boolean(
        string='Loại bắt buộc', default=True,
        help='Chuẩn phân loại bắt buộc và tuỳ chọn. Con số khả dụng phụ '
             'thuộc việc có thu thập các loại TUỲ CHỌN hay không — nên '
             'không thể tuyên bố tuân thủ chuẩn chỉ bằng cách đặt tên '
             'một chỉ số.')
    is_data_gap = fields.Boolean(
        string='Là khoảng mất dữ liệu',
        help='Mất kết nối giám sát. Phải hạch toán thành một loại thời '
             'gian, không được bỏ qua và không được coi là máy chạy tốt.')

    attributable_to = fields.Selection(
        [('operator', 'Bên vận hành'),
         ('oem', 'Nhà sản xuất / bảo hành'),
         ('grid', 'Lưới điện'),
         ('environment', 'Môi trường'),
         ('force_majeure', 'Bất khả kháng'),
         ('none', 'Không quy trách nhiệm')],
        string='Thường quy cho', default='none',
        help='Gợi ý ban đầu. Trách nhiệm THẬT do điều khoản hợp đồng '
             'quyết định, và từng hợp đồng một khác nhau.')
    standard_ref = fields.Char(
        string='Viện dẫn chuẩn',
        help='Điều khoản của chuẩn mà loại này lấy ra.')
    note = fields.Text(string='Ghi chú')
    active = fields.Boolean(default=True)

    _uniq_code = models.Constraint(
        'UNIQUE(code)', 'Mã loại thời gian không được trùng.')

    @api.depends('name', 'parent_id.complete_name', 'parent_id.level')
    def _compute_complete(self):
        for c in self:
            c.complete_name = ('%s / %s' % (c.parent_id.complete_name, c.name)
                               if c.parent_id else c.name)
            c.level = (c.parent_id.level or 0) + 1 if c.parent_id else 1

    @api.depends('complete_name', 'code')
    def _compute_display_name(self):
        for c in self:
            c.display_name = '[%s] %s' % (c.code or '', c.complete_name or '')
