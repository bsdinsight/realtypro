# -*- coding: utf-8 -*-
"""Hồ sơ cấu hình tờ báo cáo ngày — MỘT bộ máy, nhiều loại nhà máy.

Vì sao là hồ sơ cấu hình chứ không phải hai báo cáo
---------------------------------------------------
Tờ báo cáo ngày của điện mặt trời và của điện gió khác nhau ở **nội
dung từng dòng**, không khác ở cách làm việc: cùng là gom số đo trong
ngày, cùng chừng mười ô người trực tự điền, cùng chốt lại rồi gửi đi.
Viết hai báo cáo thì mọi sửa về sau phải làm hai lần, và lần thứ hai là
lần bị quên — đã thấy đúng kiểu đó ở hai bộ tính chiết khấu bên CRM.

Nên dòng trên tờ là **dữ liệu**: mỗi dòng khai nhãn in ra, đơn vị, và
lấy số từ đâu. Thêm loại nhà máy thứ ba là thêm một hồ sơ, không đụng
tới mã.

Ô NGƯỜI NHẬP tách khỏi ô MÁY TÍNH
----------------------------------
Người trực mỗi sáng chỉ nên chạm vào chừng mười ô: quan trắc bằng mắt,
nhân sự có mặt, khách đến, sự cố an toàn, nhận xét. Phần còn lại máy đã
có số rồi — bắt họ chép lại là mời sai số vào, và là cách chắc chắn nhất
để tờ báo cáo không khớp với chính hệ sinh ra nó.

Cờ ``nguon`` quyết định điều đó: ``nguoi`` thì ô mở để gõ, còn lại thì
khoá và do máy rót.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

#: Khối trên tờ báo cáo. Thứ tự này là thứ tự in.
KHOI = [
    ('khi_tuong', 'Khí tượng'),
    ('to_may', 'Từng tổ máy'),
    ('san_luong', 'Sản lượng'),
    ('cong_to', 'Công-tơ giao nhận'),
    ('ton_that', 'Tổn thất qua các bậc'),
    ('hieu_suat', 'Hiệu suất'),
    ('kha_dung', 'Khả dụng'),
    ('dung_may', 'Dừng máy'),
    ('nhan_su', 'Nhân sự & an toàn'),
    ('ghi_chu', 'Nhận xét'),
]

#: Nguồn lấy số. Mỗi nhánh là một bảng đã có sẵn số của NGÀY đó —
#: báo cáo ngày không tính lại, nó LẮP RÁP.
NGUON = [
    ('weather', 'Khí tượng trong ngày'),
    ('kpi', 'Hiệu suất điện mặt trời'),
    ('chain', 'Bậc đo trong chuỗi'),
    ('avail', 'Khả dụng trong ngày'),
    ('downtime', 'Giờ dừng theo nhóm'),
    ('historian', 'Kho chuỗi thời gian'),
    ('unit', 'Tổng bảng tổ máy'),
    ('target', 'Mục tiêu sản lượng'),
    ('khoi', 'Khối dựng sẵn (bảng, biểu đồ)'),
    ('nguoi', 'Người trực tự điền'),
]

#: Khối dựng sẵn — không phải một con số mà cả một mảng của tờ giấy.
#: Đặt chúng thành DÒNG cấu hình để thứ tự in vẫn do hồ sơ quyết, thay
#: vì chôn vào bản in rồi muốn đổi chỗ phải sửa mã.
KHOI_DAC_BIET = [
    ('bang_to_may', 'Bảng từng tổ máy'),
    ('hoa_gio', 'Hoa gió'),
    ('bieu_do_ngay', 'Biểu đồ công suất trong ngày'),
    ('cong_to', 'Công-tơ: số đọc hôm qua / hôm nay / chênh'),
]

#: Cách rút một con số NGÀY ra từ chuỗi thời gian.
CACH_LAY = [
    ('gop', 'Gộp theo cách của chính điểm đo'),
    ('dinh', 'Đỉnh trong ngày'),
    ('dinh_luc', 'Thời điểm đạt đỉnh'),
    ('gio_tren_nguong', 'Số giờ trên ngưỡng'),
]


class EamDailyProfile(models.Model):
    _name = 'eam.daily.profile'
    _description = 'Hồ sơ cấu hình báo cáo ngày'
    _order = 'name'

    name = fields.Char(string='Tên hồ sơ', required=True)
    code = fields.Char(string='Mã', required=True)
    loai = fields.Selection(
        [('pv', 'Điện mặt trời'), ('wind', 'Điện gió'), ('khac', 'Khác')],
        string='Loại nhà máy', required=True, default='khac')
    tieu_de = fields.Char(
        string='Tiêu đề in ra', required=True,
        help='Dòng tiêu đề trên bản in. Giữ đúng chữ của khách để đặt '
             'cạnh tờ cũ là so được.')
    line_ids = fields.One2many(
        'eam.daily.profile.line', 'profile_id', string='Dòng trên tờ',
        copy=True)
    line_count = fields.Integer(compute='_compute_dem', store=True)
    so_o_nguoi = fields.Integer(
        string='Số ô người trực phải điền', compute='_compute_dem',
        store=True,
        help='Con số này là lời hứa với người trực. Quá mười lăm ô thì '
             'tờ báo cáo quay về thành việc chép tay, và người ta sẽ '
             'điền cho xong chứ không điền cho đúng.')
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', default=lambda s: s.env.company)
    note = fields.Text(string='Ghi chú')

    _code_uniq = models.Constraint('unique(code, company_id)',
                                   'Mã hồ sơ đã có rồi.')

    @api.depends('line_ids', 'line_ids.nguon')
    def _compute_dem(self):
        for p in self:
            p.line_count = len(p.line_ids)
            p.so_o_nguoi = len(p.line_ids.filtered(
                lambda l: l.nguon == 'nguoi'))


class EamDailyProfileLine(models.Model):
    _name = 'eam.daily.profile.line'
    _description = 'Dòng trên tờ báo cáo ngày'
    _order = 'profile_id, khoi, sequence, id'

    profile_id = fields.Many2one(
        'eam.daily.profile', required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    khoi = fields.Selection(KHOI, string='Khối', required=True,
                            default='san_luong', index=True)
    name = fields.Char(
        string='Nhãn in ra', required=True,
        help='Đúng chữ trên tờ của khách, kể cả khi hệ gọi tên khác.')
    don_vi = fields.Char(string='Đơn vị')
    so_le = fields.Integer(string='Số lẻ', default=2)
    kieu = fields.Selection(
        [('so', 'Số'), ('chu', 'Chữ')], string='Kiểu giá trị',
        required=True, default='so')

    nguon = fields.Selection(NGUON, string='Lấy số từ đâu', required=True,
                             default='nguoi')
    truong = fields.Char(
        string='Tên trường',
        help='Tên kỹ thuật của trường trên bảng nguồn, ví dụ '
             '"irradiation" hay "kd_thoi_gian". Khai sai thì nhật ký nói '
             'rõ bảng đó có những trường nào.')
    node_code = fields.Char(
        string='Mã bậc đo',
        help='Chỉ dùng khi lấy từ chuỗi bậc đo: INV, MCB, GNT, EVN…')
    group_id = fields.Many2one(
        'eam.time.group', string='Nhóm giờ dừng',
        help='Để trống thì lấy TỔNG mọi nhóm.')
    khoi_dac_biet = fields.Selection(
        KHOI_DAC_BIET, string='Khối dựng sẵn',
        help='Chỉ dùng khi nguồn là "Khối dựng sẵn". Dòng này không mang '
             'một con số — nó đánh dấu chỗ bản in chèn cả một mảng.')
    muc = fields.Selection(
        [('p50', 'P50'), ('p75', 'P75'), ('p90', 'P90')],
        string='Mức xác suất',
        help='Chỉ dùng khi nguồn là "Mục tiêu sản lượng".')
    tag_code = fields.Char(
        string='Mã điểm đo',
        help='Gọi điểm đo theo MÃ, không theo bản ghi: hồ sơ cấu hình '
             'phải dùng được cho mọi nhà máy cùng loại, mà mỗi nhà máy '
             'có bộ điểm đo riêng. Kết thúc bằng "*" để khớp nhiều điểm '
             '— "T*_P" là công suất mọi tua-bin.')
    gop_nhieu = fields.Selection(
        [('tong', 'Cộng lại'), ('tb', 'Trung bình'), ('max', 'Lớn nhất')],
        string='Nhiều điểm đo thì gộp kiểu gì',
        help='Bắt buộc khi mã khớp nhiều hơn một điểm đo. Cộng công suất '
             'các tua-bin ra công suất nhà máy thì đúng; cộng nhiệt độ '
             'thì vô nghĩa — nên hệ KHÔNG đoán, mã khớp nhiều mà chưa '
             'khai thì dòng đó báo thiếu khai báo.')
    cach_lay = fields.Selection(
        CACH_LAY, string='Cách rút số ngày', default='gop')
    nguong = fields.Float(
        string='Ngưỡng', digits=(16, 3),
        help='Dùng cho "số giờ trên ngưỡng": giờ hoà lưới là số giờ công '
             'suất lớn hơn 0.')
    he_so = fields.Float(
        string='Hệ số nhân', default=1.0, digits=(16, 6),
        help='Nguồn ghi bằng MWh mà tờ in bằng kWh thì để 1000. Đây là '
             'chỗ sai thầm lặng nhất của mọi tờ báo cáo.')

    ghi_nguoc = fields.Boolean(
        string='Người trực điền, ghi ngược về bảng nguồn',
        help='Quan trắc bằng mắt (trời 6–9h, 9–12h…) là DỮ LIỆU KHÍ '
             'TƯỢNG — nhà của nó là sổ quan trắc, không phải tờ báo '
             'cáo. Nhưng bắt người trực mở hai màn hình mỗi sáng thì '
             'họ sẽ bỏ một màn. Cờ này cho ô mở ngay trên tờ, và hệ ghi '
             'thẳng vào sổ quan trắc — một nhà, một màn hình.')
    bat_buoc = fields.Boolean(
        string='Bắt buộc điền',
        help='Ô người trực phải điền thì mới chốt được tờ. Dùng cho '
             'những ô mà để trống là tờ báo cáo mất nghĩa.')
    goi_y = fields.Char(string='Gợi ý nhập')
    in_khi_trong = fields.Boolean(
        string='In cả khi trống', default=True,
        help='Bỏ cờ này thì dòng không có số sẽ biến mất khỏi bản in. '
             'Cân nhắc: dòng biến mất là người đọc không biết nó từng '
             'tồn tại.')
    note = fields.Char(string='Ghi chú')

    @api.constrains('nguon', 'truong', 'node_code', 'tag_code',
                    'khoi_dac_biet', 'muc')
    def _check_khai_du(self):
        for l in self:
            if l.nguon in ('weather', 'kpi', 'avail') and not l.truong:
                raise ValidationError(_(
                    'Dòng "%s" lấy số từ một bảng có sẵn thì phải khai '
                    'tên trường.', l.name))
            if l.nguon == 'chain' and not (l.node_code and l.truong):
                raise ValidationError(_(
                    'Dòng "%s" lấy từ chuỗi bậc đo thì phải khai CẢ mã '
                    'bậc lẫn tên trường.', l.name))
            if l.nguon == 'khoi' and not l.khoi_dac_biet:
                raise ValidationError(_(
                    'Dòng "%s" là khối dựng sẵn thì phải chọn khối nào.',
                    l.name))
            if l.nguon == 'target' and not l.muc:
                raise ValidationError(_(
                    'Dòng "%s" lấy mục tiêu thì phải chọn mức P50, P75 '
                    'hay P90 — "mục tiêu" không kèm mức là câu nói dở.',
                    l.name))
            if l.nguon == 'unit' and not l.truong:
                raise ValidationError(_(
                    'Dòng "%s" lấy từ bảng tổ máy thì phải khai lấy ô '
                    'nào của dòng TỔNG.', l.name))
            if l.nguon == 'historian' and not l.tag_code:
                raise ValidationError(_(
                    'Dòng "%s" lấy từ kho chuỗi thời gian thì phải khai '
                    'mã điểm đo.', l.name))

    @api.onchange('nguon')
    def _onchange_nguon(self):
        if self.nguon == 'nguoi':
            self.truong = self.node_code = self.tag_code = False
            self.cach_lay = self.gop_nhieu = False
