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
    # Phần khai KIỂU Ô dùng chung với bước kế hoạch và dòng mẫu biểu —
    # khai ba lần thì ba chỗ sẽ lệch nhau.
    _inherit = ['eam.form.field.mixin']
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
        # người và giờ ở đây để mọi đường ghi đều có vết. Cờ "đã nhập số
        # đo" cũng phải đóng ở đây, vì app hiện trường ghi thẳng bằng API
        # chứ không đi qua onchange của web.
        if 'value_num' in vals and vals.get('value_num') is not None:
            vals.setdefault('value_num_set', True)
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

    # ------------------------------------------------------------------
    # Phần TRẢ LỜI có kiểu — để tiêu chuẩn thành thứ máy đọc được
    # ------------------------------------------------------------------
    value_num = fields.Float(
        string='Số đo được', digits=(16, 4),
        help='Dùng cho ô kiểu "Số đo". Có cận dưới/cận trên thì hệ thống '
             'TỰ kết luận đạt hay không — người làm khỏi phải tự chấm.')
    # PHẢI có cờ riêng cho "đã đo chưa".
    #
    # Trường Float của Odoo đọc ra 0.0 kể cả khi chưa ai nhập gì, nên nếu
    # chỉ nhìn `value_num` thì mọi bước VỪA SINH RA có cận dưới đều bị
    # kết luận KHÔNG ĐẠT ngay lập tức — người thợ mở lệnh ra đã thấy đỏ
    # toàn bộ trước khi chạm vào cái gì, và con số "bước máy xét không
    # đạt" thành rác.
    value_num_set = fields.Boolean(
        string='Đã nhập số đo', copy=False, readonly=True)
    value_bool = fields.Boolean(string='Có / Không')
    value_sel = fields.Char(
        string='Lựa chọn',
        help='Phải là một trong các lựa chọn đã khai. Trên web đây là ô '
             'chữ có kiểm; danh sách thả xuống nằm ở app hiện trường, nơi '
             'người làm thực sự nhập.')

    auto_result = fields.Selection(
        [('ok', 'Số đo ĐẠT'),
         ('not_ok', 'Số đo KHÔNG ĐẠT'),
         ('unknown', 'Chưa xét được')],
        string='Máy xét', compute='_compute_auto_result',
        help='Kết luận rút ra từ số đo và tiêu chuẩn, không phải từ người '
             'làm tự chấm.')
    spec_display = fields.Char(
        string='Tiêu chuẩn', compute='_compute_spec_display',
        help='Gộp tiêu chuẩn khai bằng chữ và tiêu chuẩn máy đọc được.')

    @api.depends('field_type', 'value_num', 'value_num_set', 'value_min',
                 'value_max', 'has_range')
    def _compute_auto_result(self):
        for s in self:
            xet = s._xet_so_do(
                s.value_num if (s.field_type == 'number' and s.value_num_set)
                else None)
            s.auto_result = ('unknown' if xet is None
                             else 'ok' if xet else 'not_ok')

    @api.depends('spec', 'field_type', 'value_min', 'value_max',
                 'uom_label', 'has_range')
    def _compute_spec_display(self):
        for s in self:
            may = s._mo_ta_tieu_chuan()
            s.spec_display = ' · '.join(x for x in (s.spec, may) if x) or False

    @api.onchange('value_num')
    def _onchange_value_num(self):
        """Nhập số xong thì kết quả tự theo — không để người làm tự chấm.

        Đây là chỗ cả tính năng này có nghĩa: để người thợ tự kết luận
        thì lúc mệt, lúc muộn, lúc sắp hết ca, kết luận sẽ trôi — và đó
        đúng là lúc hay bỏ sót nhất.
        """
        for s in self:
            s.value_num_set = True
            # Gán xong cờ thì phải tính lại trước khi đọc — trong onchange
            # thì trường tính chưa tự chạy lại.
            s._compute_auto_result()
            if s.auto_result in ('ok', 'not_ok'):
                s.result = s.auto_result

    @api.constrains('result', 'value_num', 'value_num_set', 'field_type',
                    'value_min', 'value_max', 'has_range')
    def _check_so_do_khop_tieu_chuan(self):
        for s in self:
            if s.result != 'ok' or not s.has_range or not s.value_num_set:
                continue
            if s._xet_so_do(s.value_num) is False:
                raise ValidationError(_(
                    'Bước "%(ten)s": đo được %(do)s%(dv)s nhưng tiêu chuẩn '
                    'là %(tc)s — không ghi ĐẠT được.\n\nNếu số đo đúng thì '
                    'ghi KHÔNG ĐẠT rồi mở lệnh khắc phục. Nếu tiêu chuẩn '
                    'sai thì sửa ở kế hoạch hoặc mẫu biểu, đừng sửa ở đây.',
                    ten=s.name, do=s.value_num,
                    dv=(' ' + s.uom_label) if s.uom_label else '',
                    tc=s._mo_ta_tieu_chuan()))

    @api.constrains('result', 'value_sel', 'selection_values', 'field_type')
    def _check_lua_chon(self):
        for s in self:
            if s.field_type != 'selection' or s.result == 'pending':
                continue
            cho_phep = [x.strip() for x in (s.selection_values or '').split(',')
                        if x.strip()]
            if cho_phep and (s.value_sel or '').strip() not in cho_phep:
                raise ValidationError(_(
                    'Bước "%(ten)s": "%(gt)s" không nằm trong các lựa chọn '
                    'đã khai (%(ds)s).',
                    ten=s.name, gt=s.value_sel or '', ds=', '.join(cho_phep)))

    @api.constrains('result', 'requires_photo', 'attachment_ids')
    def _check_bat_buoc_anh(self):
        for s in self:
            if s.requires_photo and s.result in ('ok', 'not_ok') \
                    and not s.attachment_ids:
                raise ValidationError(_(
                    'Bước "%s" bắt buộc có ảnh. Bước này được khai là thứ '
                    'mà lời nói không đủ — đính ảnh vào rồi mới ghi kết '
                    'quả.', s.name))
