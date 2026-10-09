# -*- coding: utf-8 -*-
from odoo import api, fields, models


class RpErectionGate(models.Model):
    """Cổng dựng máy — một bước phải qua ở MỌI vị trí.

    Vì sao không dùng thẳng lịch thi công
    -------------------------------------
    Lịch của tổng thầu gom theo **lô vận chuyển** và **nhánh điện**: một
    việc "Feeder 6 — 4 WTGS (10-13)" ôm bốn trụ. Đó không phải lỗi lập
    lịch mà là cách họ thật sự thi công — ép lịch xuống từng trụ sẽ làm
    nó phình gấp mấy lần mà vẫn không ai cập nhật nổi.

    Nhưng quản lý lại cần biết **trụ số 7 đang kẹt ở đâu**. Nên cần một
    sổ riêng, mịn hơn lịch: mỗi vị trí × mỗi cổng = một dòng. Ngoài đời
    site manager nào cũng giữ sổ này, thường bằng Excel.

    Hai thứ làm nó khác một bảng đánh dấu
    -------------------------------------
    **① Cổng có TRỌNG SỐ.** Đổ móng nặng hơn hẳn đấu một đầu cáp. Đếm
    "7/9 cổng xong = 78%" là sai: nó coi mọi bước như nhau, và đường
    cong tiến độ vẽ ra không giống thực tế chút nào.

    **② Cổng gắn với HẠNG MỤC.** Nhờ vậy phần trăm hạng mục suy ngược
    được từ số vị trí đã qua cổng — *13/30 móng xong* — thay vì để ai đó
    gõ tay "45%". Số gõ tay không kiểm chứng được; số đếm từ 30 vị trí
    thì có.
    """
    _name = 'rp.erection.gate'
    _description = 'Cổng dựng máy'
    _order = 'sequence, code'

    name = fields.Char(string='Tên cổng', required=True, translate=True)
    code = fields.Char(string='Mã', required=True, index=True)
    sequence = fields.Integer(
        string='Thứ tự', default=10, required=True,
        help='Thứ tự thi công thật. Dùng để biết vị trí đang ĐỨNG ở cổng '
             'nào, và để phát hiện trường hợp qua cổng sau mà cổng trước '
             'chưa xong.')
    weight = fields.Float(
        string='Trọng số', default=1.0, required=True, digits=(16, 2),
        help='Đổ móng nặng hơn hẳn đấu một đầu cáp. Đếm số cổng đã qua '
             'rồi chia đều là coi mọi bước như nhau — đường cong tiến độ '
             'vẽ ra sẽ không giống thực tế.')
    structure_id = fields.Many2one(
        'rp.structure', string='Thuộc hạng mục', ondelete='set null',
        index=True,
        help='Khai vào thì hạng mục suy được phần trăm VẬT LÝ từ số vị '
             'trí đã qua cổng, thay vì nhận một con số gõ tay.')
    note = fields.Text(string='Mô tả / tiêu chí nghiệm thu')
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', string='Công ty', required=True,
        default=lambda self: self.env.company, index=True)

    step_ids = fields.One2many(
        'rp.erection.step', 'gate_id', string='Theo từng vị trí')
    done_count = fields.Integer(
        string='Số vị trí đã qua', compute='_compute_thong_ke')
    total_count = fields.Integer(
        string='Tổng vị trí', compute='_compute_thong_ke')
    percent = fields.Float(
        string='% vị trí đã qua', compute='_compute_thong_ke',
        digits=(16, 1), aggregator=False)

    _uniq_code = models.Constraint(
        'UNIQUE(company_id, code)', 'Mã cổng không được trùng.')

    @api.depends('step_ids.state')
    def _compute_thong_ke(self):
        for g in self:
            g.total_count = len(g.step_ids)
            g.done_count = len(g.step_ids.filtered(
                lambda s: s.state == 'done'))
            g.percent = (g.done_count / g.total_count * 100.0
                         if g.total_count else 0.0)

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for g in self:
            g.display_name = '[%s] %s' % (g.code or '', g.name or '')
