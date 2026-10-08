# -*- coding: utf-8 -*-
from odoo import api, fields, models


class EamFailureMode(models.Model):
    """Dạng hỏng — *hỏng thế nào*, không phải *hỏng vì sao*.

    Ba thứ hay bị gộp làm một, và gộp thì mất sạch khả năng phân tích:

    * **Dạng hỏng** (failure mode) — biểu hiện quan sát được: rò dầu, quá
      nhiệt, rung vượt ngưỡng, không khởi động được.
    * **Cơ chế hỏng** (failure mechanism) — quá trình vật lý dẫn tới:
      mỏi, mài mòn, ăn mòn, lão hoá cách điện.
    * **Nguyên nhân gốc** (root cause) — vì sao cơ chế đó xảy ra: lắp
      sai lực siết, bôi trơn thiếu, lỗi thiết kế, lỗi lô hàng.

    Một dạng hỏng ứng với nhiều cơ chế, một cơ chế ứng với nhiều nguyên
    nhân. Nhập cả ba vào một ô văn bản tự do thì vài năm sau không trả
    lời được câu *"hộp số của đội máy này hỏng theo kiểu gì nhiều nhất"*
    — câu quyết định nên siết bảo trì phòng ngừa ở đâu.

    ``category_id`` gắn dạng hỏng với loại cấu phần, vì danh mục dạng
    hỏng của cánh quạt không dùng được cho bộ biến đổi công suất. Để
    trống nghĩa là dùng cho mọi loại.
    """
    _name = 'eam.failure.mode'
    _description = 'Dạng hỏng'
    _order = 'category_id, code'

    name = fields.Char(string='Dạng hỏng', required=True, translate=True)
    code = fields.Char(string='Mã', required=True, index=True)
    category_id = fields.Many2one(
        'eam.asset.category', string='Loại cấu phần', ondelete='restrict',
        index=True,
        help='Để trống nghĩa là dùng cho mọi loại. Khai vào thì chỉ hiện '
             'khi lệnh công việc đúng loại cấu phần đó — danh mục dạng '
             'hỏng của cánh quạt không dùng được cho bộ biến đổi.')
    mechanism = fields.Selection(
        [('fatigue', 'Mỏi'),
         ('wear', 'Mài mòn'),
         ('corrosion', 'Ăn mòn'),
         ('overload', 'Quá tải'),
         ('insulation', 'Lão hoá cách điện'),
         ('contamination', 'Nhiễm bẩn, lẫn tạp'),
         ('lubrication', 'Bôi trơn không đủ'),
         ('loosening', 'Lỏng liên kết'),
         ('software', 'Lỗi điều khiển, phần mềm'),
         ('external', 'Tác động bên ngoài'),
         ('unknown', 'Chưa xác định')],
        string='Cơ chế hỏng thường gặp', default='unknown',
        help='GỢI Ý, không phải kết luận. Cơ chế thật của từng lần hỏng '
             'khai trên chính lệnh công việc.')
    standard_ref = fields.Char(
        string='Viện dẫn chuẩn',
        help='Mã hoặc điều khoản của bộ chuẩn mà dạng hỏng này lấy ra.')
    note = fields.Text(string='Ghi chú')
    active = fields.Boolean(default=True)

    _uniq_code = models.Constraint(
        'UNIQUE(code)', 'Mã dạng hỏng không được trùng.')

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for m in self:
            m.display_name = '[%s] %s' % (m.code or '', m.name or '')
