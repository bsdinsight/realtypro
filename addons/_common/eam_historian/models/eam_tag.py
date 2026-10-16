# -*- coding: utf-8 -*-
"""Sổ điểm đo (tag) — phần SIÊU DỮ LIỆU của historian.

Số đo KHÔNG nằm ở đây. Chúng nằm trong bảng `eam_tag_reading` viết
bằng SQL thuần (xem ``eam_historian.py``); model này chỉ khai *điểm đo
là gì*, *đơn vị gì*, *gộp lên bằng cách nào*, và *thế nào là số vô lý*.

Hai chỗ một historian hay làm sai, và sai IM LẶNG
==================================================

**① Gộp sai cách.** Đây là lỗi tệ nhất vì kết quả trông vẫn hợp lý.

* Công suất (kW) gộp bằng **trung bình** — đúng.
* Điện năng luỹ kế (kWh, đồng hồ chỉ tăng) gộp bằng trung bình là ra
  một con số vô nghĩa. Phải lấy **hiệu đầu-cuối** của khoảng.
* Trạng thái (chạy/dừng) phải lấy **giá trị cuối**, trung bình của 0 và
  1 không có nghĩa gì.
* **Hướng gió thì không gộp số học được.** Trung bình của 350° và 10°
  ra 180° — tức là ngược hẳn hướng thật (0°). Phải lấy trung bình
  VECTƠ. Hệ nào bỏ qua chuyện này sẽ vẽ ra hoa gió sai hoàn toàn, mà
  biểu đồ vẫn mượt và không ai nghi ngờ.

**② Vứt số đo "xấu".** Lọc outlier xong xoá luôn bản gốc thì không bao
giờ chứng minh lại được, và yêu cầu R05 nói rõ *không xoá, không nén
mất mát dữ liệu gốc*. Nên ở đây luật làm sạch chỉ **đóng cờ chất
lượng**; số thô giữ nguyên vĩnh viễn, còn người đọc tự chọn có lọc theo
cờ hay không.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

LOAI_DO = [
    ('power', 'Công suất (kW)'),
    ('energy', 'Điện năng luỹ kế (kWh)'),
    ('wind_speed', 'Tốc độ gió (m/s)'),
    ('wind_dir', 'Hướng gió (độ)'),
    ('irradiance', 'Bức xạ (W/m²)'),
    ('temperature', 'Nhiệt độ (°C)'),
    ('pressure', 'Áp suất'),
    ('vibration', 'Độ rung'),
    ('rotation', 'Tốc độ quay (vòng/phút)'),
    ('status', 'Trạng thái (0/1)'),
    ('counter', 'Bộ đếm'),
    ('other', 'Khác'),
]

# Cách gộp nhiều số đo thành một điểm trên biểu đồ.
CACH_GOP = [
    ('avg', 'Trung bình'),
    ('sum', 'Cộng dồn'),
    ('min', 'Nhỏ nhất'),
    ('max', 'Lớn nhất'),
    ('last', 'Giá trị cuối'),
    ('counter_delta', 'Hiệu đầu–cuối (đồng hồ luỹ kế)'),
    ('vector_avg', 'Trung bình VECTƠ (hướng gió)'),
]

# Gợi ý cách gộp theo loại đo. Chỉ là GỢI Ý lúc chọn loại — người khai
# vẫn đổi được, vì cùng một loại vẫn có ngoại lệ.
GOI_Y_GOP = {
    'power': 'avg', 'energy': 'counter_delta', 'wind_speed': 'avg',
    'wind_dir': 'vector_avg', 'irradiance': 'avg', 'temperature': 'avg',
    'pressure': 'avg', 'vibration': 'max', 'rotation': 'avg',
    'status': 'last', 'counter': 'counter_delta', 'other': 'avg',
}

# Cờ chất lượng — BITMASK, vì một số đo có thể sai nhiều kiểu cùng lúc.
CO_TOT = 0
CO_NGOAI_DAI = 1
CO_NHAY_NHANH = 2
CO_KET = 4
CO_NOI_SUY = 8
CO_NGUON_NGHI = 16

NHAN_CO = {
    CO_NGOAI_DAI: 'ngoài dải hợp lý',
    CO_NHAY_NHANH: 'nhảy quá nhanh',
    CO_KET: 'kẹt (lặp lại y hệt)',
    CO_NOI_SUY: 'nội suy / bù',
    CO_NGUON_NGHI: 'nguồn nghi ngờ',
}


def mo_ta_co(q):
    """Diễn giải bitmask chất lượng thành chữ người đọc được."""
    if not q:
        return ''
    return ', '.join(t for b, t in NHAN_CO.items() if q & b)


class EamTag(models.Model):
    _name = 'eam.tag'
    _description = 'Điểm đo (tag) của historian'
    _inherit = ['mail.thread']
    _order = 'location_id, code'

    name = fields.Char(string='Tên điểm đo', required=True, tracking=True)
    code = fields.Char(
        string='Mã tag', required=True, index=True, tracking=True,
        help='Mã dùng trong công thức tag tính toán và trong lệnh nạp dữ '
             'liệu từ hệ giám sát. Đổi mã là làm hỏng mọi công thức đang '
             'trỏ vào nó.')
    active = fields.Boolean(default=True, tracking=True)
    note = fields.Text(string='Diễn giải')

    location_id = fields.Many2one(
        'eam.location', string='Vị trí', required=True, ondelete='restrict',
        index=True, tracking=True)
    asset_id = fields.Many2one(
        'eam.asset', string='Thiết bị', compute='_compute_asset', store=True,
        readonly=False, index=True)
    plant_id = fields.Many2one(
        related='location_id.plant_id', store=True, index=True,
        string='Nhà máy')

    tag_type = fields.Selection(
        LOAI_DO, string='Loại đo', required=True, default='power',
        tracking=True)
    uom_label = fields.Char(string='Đơn vị', tracking=True)
    aggregation = fields.Selection(
        CACH_GOP, string='Cách gộp', required=True, default='avg',
        tracking=True,
        help='Quyết định con số hiện trên biểu đồ. Gộp sai thì kết quả '
             'VẪN TRÔNG HỢP LÝ: điện năng luỹ kế lấy trung bình ra một số '
             'vô nghĩa, hướng gió lấy trung bình số học ra ngược hướng '
             'thật. Đây là chỗ sai im lặng nhất của cả historian.')

    source = fields.Selection(
        [('scada', 'Hệ giám sát (SCADA/OPC)'),
         ('meter', 'Công-tơ, đồng hồ'),
         ('weather', 'Trạm khí tượng'),
         ('manual', 'Nhập tay'),
         ('calc', 'Tag tính toán'),
         ('external', 'Hệ ngoài đẩy vào')],
        string='Nguồn', required=True, default='scada', tracking=True)
    sample_seconds = fields.Integer(
        string='Nhịp lấy mẫu (giây)', default=60, required=True,
        help='Nhịp DỰ KIẾN. Dùng để phát hiện mất dữ liệu: thưa hơn nhịp '
             'này nhiều lần nghĩa là có khoảng trống, chứ không phải máy '
             'đứng im.')

    # ------------------------------------------------------------------
    # Tag tính toán (C04)
    # ------------------------------------------------------------------
    is_virtual = fields.Boolean(
        string='Tag tính toán', tracking=True,
        help='Không có số đo riêng — tính ra từ các tag khác mỗi lần đọc.')
    formula = fields.Char(
        string='Công thức',
        help='Viết bằng MÃ TAG, ví dụ: (E_AC / (G_POA * P_NOM)) * 100. '
             'Tính lúc ĐỌC chứ không lưu sẵn, nên sửa công thức là mọi '
             'biểu đồ cũ cũng đổi theo — đó là điều mong muốn: công thức '
             'sai thì phải sai ở mọi chỗ, không để lại số cũ tính bằng '
             'công thức cũ mà không ai biết.')

    # ------------------------------------------------------------------
    # Làm sạch dữ liệu (C05) — chỉ ĐÓNG CỜ, không bao giờ xoá
    # ------------------------------------------------------------------
    check_range = fields.Boolean(string='Kiểm dải hợp lý', default=True)
    value_min = fields.Float(string='Nhỏ nhất hợp lý', digits=(16, 4))
    value_max = fields.Float(string='Lớn nhất hợp lý', digits=(16, 4))
    max_rate = fields.Float(
        string='Biến thiên tối đa (đơn vị/giây)', digits=(16, 4),
        help='Vượt mức này thì đánh dấu "nhảy quá nhanh". Để 0 là không '
             'kiểm. Bức xạ không thể nhảy 800 W/m² trong một giây, nhưng '
             'một đầu đo hỏng thì có.')
    stuck_count = fields.Integer(
        string='Coi là KẸT sau … lần lặp y hệt', default=0,
        help='Đầu đo chết thường trả về đúng một giá trị mãi, và giá trị '
             'đó nằm trong dải hợp lý nên kiểm dải không bắt được. Để 0 '
             'là không kiểm.')

    # Kỹ thuật: độ dài chuỗi giá trị lặp y hệt tính tới số đo cuối.
    # Phải giữ giữa các lô — một đầu đo chết trải qua nhiều lô nạp sẽ
    # không bao giờ đủ ngưỡng nếu mỗi lô đếm lại từ đầu.
    stuck_run = fields.Integer(string='Chuỗi lặp hiện tại', readonly=True,
                               copy=False)

    retention_years = fields.Integer(
        string='Giữ dữ liệu (năm)', default=10, required=True,
        help='Mặc định 10 năm theo yêu cầu "bằng chứng vận hành thực tế". '
             'Hệ thống KHÔNG tự xoá — con số này chỉ để báo cáo và để '
             'người quản trị biết cam kết là bao nhiêu.')

    # ------------------------------------------------------------------
    reading_count = fields.Integer(
        string='Số bản ghi', compute='_compute_thong_ke',
        search='_search_reading_count')
    first_ts = fields.Datetime(string='Số đo đầu', compute='_compute_thong_ke')
    last_ts = fields.Datetime(string='Số đo cuối', compute='_compute_thong_ke')
    last_value = fields.Float(string='Giá trị cuối', digits=(16, 4),
                              compute='_compute_thong_ke')
    suspect_count = fields.Integer(
        string='Số đo bị đánh dấu', compute='_compute_thong_ke',
        help='Số bản ghi mang cờ chất lượng khác "tốt". Chúng VẪN NẰM '
             'nguyên trong kho — cờ chỉ để người đọc tự quyết có lọc hay '
             'không.')

    company_id = fields.Many2one(
        related='location_id.company_id', store=True, index=True)

    _uniq_code = models.Constraint(
        'UNIQUE(company_id, code)', 'Mã tag không được trùng.')

    # ------------------------------------------------------------------
    @api.depends('location_id')
    def _compute_asset(self):
        I = self.env['eam.installation']
        hn = fields.Date.context_today(self)
        for t in self:
            if not t.location_id:
                t.asset_id = False
                continue
            lap = I.search(
                [('location_id', '=', t.location_id.id),
                 ('date_install', '<=', hn),
                 '|', ('date_remove', '=', False),
                 ('date_remove', '>=', hn)],
                order='date_install desc', limit=1)
            t.asset_id = lap.asset_id.id if lap else False

    @api.onchange('tag_type')
    def _onchange_tag_type(self):
        """Gợi ý cách gộp theo loại đo — gợi ý, không ép."""
        if self.tag_type:
            self.aggregation = GOI_Y_GOP.get(self.tag_type, 'avg')

    def _compute_thong_ke(self):
        H = self.env['eam.historian']
        for t in self:
            tk = H.thong_ke_tag(t.id) if t.id else {}
            t.reading_count = tk.get('n', 0)
            t.first_ts = tk.get('dau') or False
            t.last_ts = tk.get('cuoi') or False
            t.last_value = tk.get('gt_cuoi') or 0.0
            t.suspect_count = tk.get('nghi', 0)

    @api.model
    def _search_reading_count(self, operator, value):
        """Tìm theo số bản ghi — số đo nằm NGOÀI ORM nên phải tự hỏi kho.

        Dùng được cho câu hỏi đáng giá nhất của một historian: *điểm đo
        nào đã khai mà chưa có số đo nào?* Đó gần như luôn là một bộ
        kết nối đang chết trong im lặng — khai xong tưởng chạy, mà
        không ai nhận ra vì màn hình chẳng báo gì.

        Chỉ hỗ trợ so với 0; so với số khác thì phải đếm toàn kho, tốn
        hơn giá trị nó mang lại.
        """
        if value != 0 or operator not in ('=', '!=', '>', '<='):
            raise UserError(_(
                'Chỉ lọc được "chưa có số đo nào" (so sánh với 0).'))
        co_du = self.env['eam.historian'].tag_co_du_lieu()
        rong = operator in ('=', '<=')
        if not rong:
            return [('id', 'in', list(co_du))]
        # Tag TÍNH TOÁN không bao giờ có số đo lưu — nó tính lúc đọc.
        # Để nó lọt vào danh sách "chưa có số đo" là báo động giả, và
        # báo động giả thì sau vài lần không ai nhìn danh sách nữa.
        return ['&', ('id', 'not in', list(co_du)),
                ('is_virtual', '=', False)]

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for t in self:
            t.display_name = '[%s] %s' % (t.code or '', t.name or '')

    @api.constrains('is_virtual', 'formula')
    def _check_cong_thuc(self):
        for t in self:
            if t.is_virtual and not (t.formula or '').strip():
                raise ValidationError(_(
                    'Tag tính toán "%s" chưa có công thức — nó sẽ không '
                    'bao giờ ra giá trị nào.', t.name))
            if t.is_virtual:
                thieu = t._tag_trong_cong_thuc() - set(
                    self.search([('code', 'in',
                                  list(t._tag_trong_cong_thuc()))]
                                ).mapped('code'))
                if thieu:
                    raise ValidationError(_(
                        'Công thức của "%(t)s" trỏ tới mã tag không tồn '
                        'tại: %(m)s.', t=t.name, m=', '.join(sorted(thieu))))

    @api.constrains('value_min', 'value_max', 'check_range')
    def _check_dai(self):
        for t in self:
            if t.check_range and t.value_min and t.value_max \
                    and t.value_min >= t.value_max:
                raise ValidationError(_(
                    'Tag "%s": cận dưới phải nhỏ hơn cận trên, nếu không '
                    'thì MỌI số đo đều bị đánh dấu ngoài dải.', t.name))

    # ------------------------------------------------------------------
    def _tag_trong_cong_thuc(self):
        """Các mã tag mà công thức này trỏ tới."""
        import re
        self.ensure_one()
        if not self.formula:
            return set()
        # Tên hợp lệ trong công thức = mã tag. Bỏ qua hàm toán học cho
        # sẵn, nếu không thì `abs(...)` bị coi là một tag không tồn tại.
        ham = {'abs', 'min', 'max', 'round', 'sqrt', 'pow'}
        return {m for m in re.findall(r'[A-Za-z_][A-Za-z0-9_]*',
                                      self.formula) if m not in ham}

    def action_xem_bieu_do(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Xu hướng — %s', self.display_name),
            'res_model': 'eam.trend.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_tag_ids': [(6, 0, self.ids)]},
        }
