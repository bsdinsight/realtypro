# -*- coding: utf-8 -*-
"""Danh mục LOẠI TỔN THẤT — khai được, không sửa mã.

Mỗi nhà máy mất điện vì những lý do khác nhau, và danh sách ấy dài ra
theo thời gian: hôm nay là bụi bẩn và cắt giảm, sang năm thêm "giới hạn
nhiệt máy biến áp". Viết cứng danh sách vào mã nghĩa là mỗi lần nhà máy
nghĩ ra một nguyên nhân mới thì phải chờ bản phát hành.

Nên loại tổn thất là DỮ LIỆU, và cách lấy số của nó cũng khai luôn —
lấy từ sổ dừng máy theo nhóm nào, hay từ bậc nào trong chuỗi điểm đo,
hay người nhập tay.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

#: Nhóm để xếp cột trên biểu đồ thác nước. Thứ tự này là thứ tự trừ:
#: tài nguyên trước (trời cho bao nhiêu), rồi mới tới những thứ con
#: người chịu trách nhiệm.
NHOM = [
    ('tai_nguyen', 'Tài nguyên — trời cho bao nhiêu'),
    ('luoi', 'Lưới & điều độ'),
    ('dung_may', 'Dừng máy'),
    ('ky_thuat', 'Kỹ thuật & suy giảm'),
    ('tu_dung', 'Tiêu thụ có chủ đích'),
    ('khac', 'Khác'),
]

CACH_DO = [
    ('dung_may', 'Sổ dừng máy — theo nhóm giờ dừng'),
    ('bac_do', 'Chuỗi điểm đo — tổn thất của một bậc'),
    ('tay', 'Người nhập tay'),
]


class EamLossType(models.Model):
    _name = 'eam.loss.type'
    _description = 'Loại tổn thất'
    _order = 'sequence, code'

    name = fields.Char(string='Tên loại', required=True, translate=True)
    code = fields.Char(string='Mã', required=True)
    sequence = fields.Integer(
        string='Thứ tự', default=10,
        help='Thứ tự TRỪ trên biểu đồ thác nước. Đổi thứ tự không đổi '
             'tổng, nhưng đổi câu chuyện tờ giấy kể.')
    nhom = fields.Selection(NHOM, string='Nhóm', required=True,
                            default='khac')
    cach_do = fields.Selection(
        CACH_DO, string='Lấy số từ đâu', required=True, default='tay',
        help='Khai ở đây thay vì viết vào mã, để nhà máy thêm nguyên '
             'nhân mới mà không phải chờ bản phát hành.')
    group_id = fields.Many2one(
        'eam.time.group', string='Nhóm giờ dừng',
        help='Chỉ dùng khi lấy số từ sổ dừng máy.')
    node_code = fields.Char(
        string='Mã bậc đo',
        help='Chỉ dùng khi lấy số từ chuỗi điểm đo.')
    la_tu_dung = fields.Boolean(
        string='Là tiêu thụ có chủ đích',
        help='Điện tự dùng và tiêu thụ ban đêm KHÔNG phải tổn thất — nhà '
             'máy cố tình dùng chúng. Vẫn trừ khỏi sản lượng bán được, '
             'nhưng xếp riêng: gộp vào tổn thất là đổ cho vận hành một '
             'khoản mà vận hành không làm gì sai.')
    note = fields.Text(string='Ghi chú')
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda s: s.env.company)

    _uniq_code = models.Constraint('UNIQUE(code, company_id)',
                                   'Mã loại tổn thất phải là duy nhất.')

    @api.constrains('cach_do', 'group_id', 'node_code')
    def _check_khai_du(self):
        for r in self:
            if r.cach_do == 'dung_may' and not r.group_id:
                raise ValidationError(_(
                    'Loại "%s" lấy số từ sổ dừng máy thì phải chọn nhóm '
                    'giờ dừng.', r.name))
            if r.cach_do == 'bac_do' and not r.node_code:
                raise ValidationError(_(
                    'Loại "%s" lấy số từ chuỗi điểm đo thì phải khai mã '
                    'bậc.', r.name))
