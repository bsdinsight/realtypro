# -*- coding: utf-8 -*-
"""Biểu mẫu động: ô nhập CÓ KIỂU, và tiêu chuẩn MÁY ĐỌC ĐƯỢC.

Vấn đề thật với checklist bằng chữ
-----------------------------------
Bước công việc hiện có một ô ``Tiêu chuẩn / trị số`` là chữ, ví dụ
*"lực siết 200–220 Nm"*, và một ô ``Trị số đo được`` cũng là chữ. Người
thợ gõ "180" rồi tự tick **Đạt**, và hệ thống nhận. Không có gì sai về
kỹ thuật — nhưng cái checklist đó **không kiểm soát được gì**: nó chỉ
là tờ giấy đã ký, chuyển từ giấy sang màn hình.

Chỗ này đổi nó thành thứ máy đọc được: khai kiểu ô (số đo / có-không /
chọn một / chữ / ảnh), và với ô số thì khai **cận dưới, cận trên, đơn
vị**. Khi đó hệ thống tự kết luận *"đo được 180 Nm, tiêu chuẩn 200–220
Nm → KHÔNG ĐẠT"*, và **không cho tick Đạt** khi số đo nằm ngoài tiêu
chuẩn.

Khác biệt nằm ở chỗ ai kết luận. Để người thợ tự kết luận thì lúc mệt,
lúc muộn, lúc sắp hết ca, kết luận sẽ trôi — và đó đúng là lúc hay bỏ
sót nhất.

Vì sao có BẢNG MẪU riêng chứ không chỉ dùng bước của kế hoạch
--------------------------------------------------------------
Bước của ``eam.pm.plan`` gắn chặt với một chu kỳ bảo trì. Nhưng nhiều
biểu mẫu **không** thuộc chu kỳ nào: phiếu cô lập nguồn (LOTO), biên
bản chạy thử, biểu mẫu kiểm tra sau bão. Chúng cần gắn được vào *bất kỳ*
lệnh nào, kể cả lệnh sửa chữa đột xuất.

Nên mẫu là một bảng riêng, còn phần khai KIỂU Ô thì dùng chung một
mixin cho cả ba nơi (bước kế hoạch, dòng mẫu, bước trên lệnh) — nếu
không thì cùng một khái niệm được khai ba lần và ba chỗ sẽ lệch nhau.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

KIEU_O = [
    ('text', 'Chữ'),
    ('number', 'Số đo'),
    ('bool', 'Có / Không'),
    ('selection', 'Chọn một'),
    ('photo', 'Ảnh'),
]


class EamFormFieldMixin(models.AbstractModel):
    """Phần KHAI BÁO của một ô nhập. Dùng chung cho mọi nơi định nghĩa bước."""
    _name = 'eam.form.field.mixin'
    _description = 'Khai báo ô nhập biểu mẫu'

    field_type = fields.Selection(
        KIEU_O, string='Kiểu ô', default='text', required=True,
        help='Chọn "Số đo" thì khai thêm cận dưới/cận trên — khi đó hệ '
             'thống tự kết luận đạt hay không, thay vì để người làm tự '
             'tick.')
    uom_label = fields.Char(
        string='Đơn vị', help='Nm, bar, °C, mm, V… Ghi ra để người đo khỏi '
                              'phải đoán đang đo bằng đơn vị gì.')
    value_min = fields.Float(string='Cận dưới', digits=(16, 4))
    value_max = fields.Float(string='Cận trên', digits=(16, 4))
    has_range = fields.Boolean(
        string='Có tiêu chuẩn máy đọc được', compute='_compute_has_range',
        store=True,
        help='Bật khi ô là Số đo và có ít nhất một cận. Chỉ khi đó hệ '
             'thống mới tự kết luận được.')
    selection_values = fields.Char(
        string='Các lựa chọn',
        help='Ngăn bằng dấu phẩy, ví dụ: Khô, Ẩm nhẹ, Ướt rõ.')
    requires_photo = fields.Boolean(
        string='Bắt buộc có ảnh',
        help='Không cho ghi kết quả khi chưa đính ảnh. Dùng cho bước mà '
             'lời nói không đủ: tình trạng mối hàn, vết nứt, mức dầu.')

    @api.depends('field_type', 'value_min', 'value_max')
    def _compute_has_range(self):
        for r in self:
            r.has_range = bool(
                r.field_type == 'number' and (r.value_min or r.value_max))

    @api.constrains('field_type', 'value_min', 'value_max',
                    'selection_values')
    def _check_khai_bao(self):
        for r in self:
            if r.field_type == 'number' and r.value_min and r.value_max \
                    and r.value_min > r.value_max:
                raise ValidationError(_(
                    'Bước "%s": cận dưới lớn hơn cận trên, nên không số đo '
                    'nào đạt được.', r.display_name or ''))
            if r.field_type == 'selection' and not (
                    r.selection_values or '').strip():
                raise ValidationError(_(
                    'Bước "%s" là ô chọn một nhưng chưa khai lựa chọn nào.',
                    r.display_name or ''))

    def _mo_ta_tieu_chuan(self):
        """Câu mô tả tiêu chuẩn, để chép sang ô chữ cho người đọc."""
        self.ensure_one()
        dv = (' ' + self.uom_label) if self.uom_label else ''
        if self.field_type != 'number' or not self.has_range:
            return ''
        if self.value_min and self.value_max:
            return _('%(a)s–%(b)s%(dv)s',
                     a=self.value_min, b=self.value_max, dv=dv)
        if self.value_min:
            return _('≥ %(a)s%(dv)s', a=self.value_min, dv=dv)
        return _('≤ %(b)s%(dv)s', b=self.value_max, dv=dv)

    def _xet_so_do(self, so):
        """Số đo này đạt không. Trả ``True`` / ``False`` / ``None`` (chưa xét được)."""
        self.ensure_one()
        if self.field_type != 'number' or not self.has_range or so is None:
            return None
        if self.value_min and so < self.value_min:
            return False
        if self.value_max and so > self.value_max:
            return False
        return True


class EamFormTemplate(models.Model):
    """Mẫu biểu gắn được vào BẤT KỲ lệnh nào, không thuộc chu kỳ bảo trì."""
    _name = 'eam.form.template'
    _description = 'Mẫu biểu công việc'
    _order = 'sequence, code'

    name = fields.Char(string='Tên mẫu', required=True)
    code = fields.Char(string='Mã', required=True, index=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    note = fields.Text(string='Dùng khi nào')
    category = fields.Selection(
        [('safety', 'An toàn, cô lập nguồn'),
         ('inspection', 'Kiểm tra, xem xét'),
         ('commissioning', 'Chạy thử, nghiệm thu'),
         ('maintenance', 'Bảo dưỡng'),
         ('storm', 'Kiểm tra sau bão, sự kiện bất thường'),
         ('other', 'Khác')],
        string='Nhóm mẫu', default='inspection', required=True, index=True)
    line_ids = fields.One2many(
        'eam.form.template.line', 'template_id', string='Các bước')
    line_count = fields.Integer(string='Số bước', compute='_compute_line')
    company_id = fields.Many2one(
        'res.company', string='Công ty', required=True,
        default=lambda self: self.env.company, index=True)

    _uniq_code = models.Constraint(
        'UNIQUE(company_id, code)', 'Mã mẫu biểu không được trùng.')

    @api.depends('line_ids')
    def _compute_line(self):
        for t in self:
            t.line_count = len(t.line_ids)

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for t in self:
            t.display_name = '[%s] %s' % (t.code or '', t.name or '')


class EamFormTemplateLine(models.Model):
    _name = 'eam.form.template.line'
    _description = 'Bước trong mẫu biểu'
    _inherit = ['eam.form.field.mixin']
    _order = 'template_id, sequence, id'

    template_id = fields.Many2one(
        'eam.form.template', string='Mẫu biểu', required=True,
        ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    name = fields.Char(string='Bước công việc', required=True)
    spec = fields.Char(string='Tiêu chuẩn / ghi chú')
    is_critical = fields.Boolean(
        string='Bước chịu lực',
        help='Bỏ hoặc làm hỏng bước này là hỏng cả lần làm. Lệnh KHÔNG '
             'đóng được khi bước chịu lực còn dở.')
    company_id = fields.Many2one(
        related='template_id.company_id', store=True, index=True)

    @api.depends('name')
    def _compute_display_name(self):
        for r in self:
            r.display_name = r.name or ''

    def _sang_buoc(self):
        """Giá trị để tạo một ``eam.work.order.step`` từ dòng mẫu này.

        KHÔNG chép mô tả tiêu chuẩn máy đọc được vào ô ``spec``: ô đó
        dành cho ghi chú bằng chữ, còn ``spec_display`` đã ghép sẵn cả
        hai. Chép vào thì tiêu chuẩn hiện ra hai lần cạnh nhau.
        """
        self.ensure_one()
        return {
            'sequence': self.sequence,
            'name': self.name,
            'spec': self.spec or False,
            'is_critical': self.is_critical,
            'field_type': self.field_type,
            'uom_label': self.uom_label,
            'value_min': self.value_min,
            'value_max': self.value_max,
            'selection_values': self.selection_values,
            'requires_photo': self.requires_photo,
        }


class EamFormApplyWizard(models.TransientModel):
    """Gắn mẫu biểu vào lệnh đang mở."""
    _name = 'eam.form.apply.wizard'
    _description = 'Gắn mẫu biểu vào lệnh'

    wo_id = fields.Many2one('eam.work.order', string='Lệnh', required=True)
    template_ids = fields.Many2many(
        'eam.form.template', string='Mẫu biểu', required=True)

    def action_gan(self):
        self.ensure_one()
        if self.wo_id.state in ('done', 'closed', 'cancelled'):
            raise UserError(_(
                'Lệnh "%s" đã khép — gắn thêm bước vào lúc này thì bước mới '
                'sẽ không bao giờ có ai làm.', self.wo_id.name))
        S = self.env['eam.work.order.step']
        bat_dau = max(self.wo_id.step_ids.mapped('sequence') or [0])
        n = 0
        for t in self.template_ids:
            for d in t.line_ids.sorted('sequence'):
                v = d._sang_buoc()
                bat_dau += 10
                v.update({'wo_id': self.wo_id.id, 'sequence': bat_dau})
                S.create(v)
                n += 1
            self.wo_id.message_post(body=_(
                'Gắn mẫu biểu %(t)s (%(n)d bước).',
                t=t.display_name, n=len(t.line_ids)))
        return {'type': 'ir.actions.act_window_close'}
