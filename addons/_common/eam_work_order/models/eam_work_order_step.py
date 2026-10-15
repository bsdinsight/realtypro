# -*- coding: utf-8 -*-
"""Bước công việc trên lệnh — thứ người thợ thật sự tick khi làm.

Model này ở tầng ``eam_work_order``, KHÔNG biết tới bảo trì phòng
ngừa — vì ``eam_pm`` phụ thuộc vào đây chứ không ngược lại. Trường
``pm_task_id`` truy ngược về bước trong kế hoạch được khai thêm bên
``eam_pm``, đúng chiều phụ thuộc.

Kế hoạch bảo trì đã có bước có cấu trúc (``eam.pm.task``: tên, tiêu
chuẩn, cờ chịu lực). Nhưng lúc sinh lệnh, chúng bị **làm phẳng thành
một đoạn chữ** trong ``description``. Hệ quả không phải là xấu màn hình:

* Người làm không tick được, nên không ai biết bước nào đã xong.
* Không ghi được TRỊ SỐ ĐO THỰC TẾ cạnh tiêu chuẩn — mà đó mới là thứ
  người kiểm tra cần đối chiếu.
* Cờ ``is_critical`` mất sạch khi sang lệnh, nên câu "bỏ bước này là
  hỏng cả lần bảo trì" không có chỗ nào siết được.
* Không đo được thời gian từng bước, nên KPI bảo trì chỉ có tổng.

Model này giữ lại cấu trúc đó tới tận lúc thi công.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

KET_QUA = [
    ('pending', 'Chưa làm'),
    ('ok', 'Đạt'),
    ('not_ok', 'Không đạt'),
    ('na', 'Không áp dụng'),
]


class EamWorkOrderStep(models.Model):
    _name = 'eam.work.order.step'
    _description = 'Bước công việc trong lệnh'
    _order = 'wo_id, sequence, id'

    wo_id = fields.Many2one(
        'eam.work.order', string='Lệnh công việc', required=True,
        ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    name = fields.Char(string='Bước công việc', required=True)
    spec = fields.Char(
        string='Tiêu chuẩn / trị số',
        help='Chép từ kế hoạch. Người làm khỏi tra sổ tay, người kiểm tra '
             'biết lấy gì để đối chiếu.')
    is_critical = fields.Boolean(
        string='Bước chịu lực',
        help='Bỏ hoặc làm hỏng bước này là hỏng cả lần bảo trì. Lệnh KHÔNG '
             'đóng được khi bước chịu lực còn dở.')
    result = fields.Selection(
        KET_QUA, string='Kết quả', default='pending', required=True,
        index=True)
    value = fields.Char(
        string='Trị số đo được',
        help='Ghi số ĐO ĐƯỢC cạnh tiêu chuẩn. Không có nó thì "đạt" chỉ là '
             'lời nói, không đối chiếu lại được.')
    note = fields.Char(string='Ghi chú')
    user_id = fields.Many2one('res.users', string='Người làm', readonly=True)
    date_done = fields.Datetime(string='Làm lúc', readonly=True)
    attachment_ids = fields.Many2many(
        'ir.attachment', string='Ảnh / chứng cứ')

    company_id = fields.Many2one(
        related='wo_id.company_id', store=True, index=True)

    # ------------------------------------------------------------------
    @api.onchange('result')
    def _onchange_result(self):
        for rec in self:
            if rec.result in ('ok', 'not_ok', 'na'):
                rec.user_id = self.env.user
                rec.date_done = fields.Datetime.now()
            else:
                rec.user_id = False
                rec.date_done = False

    def write(self, vals):
        # Ghi qua API hoặc nhập hàng loạt không chạy onchange — đóng dấu
        # người và giờ ở đây để mọi đường ghi đều có vết.
        if 'result' in vals:
            if vals['result'] in ('ok', 'not_ok', 'na'):
                vals.setdefault('user_id', self.env.uid)
                vals.setdefault('date_done', fields.Datetime.now())
            else:
                vals['user_id'] = False
                vals['date_done'] = False
        return super().write(vals)

    @api.constrains('result', 'note')
    def _check_not_ok_co_ly_do(self):
        for rec in self:
            if rec.result == 'not_ok' and not (rec.note or rec.value):
                raise ValidationError(_(
                    'Bước "%s" ghi KHÔNG ĐẠT thì phải nói rõ sai ở đâu — '
                    'điền trị số đo được hoặc ghi chú. Một chữ "không đạt" '
                    'trống trơn thì người sửa sau không biết bắt đầu từ '
                    'đâu.') % rec.name)
