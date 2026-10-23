# -*- coding: utf-8 -*-
"""Danh mục LOẠI hợp đồng trong giai đoạn vận hành.

Vì sao cần một danh mục, không phải một ô chữ
----------------------------------------------
Giai đoạn O&M của một nhà máy không chỉ có một hợp đồng. Có hợp đồng O&M
tổng, có dịch vụ dài hạn của hãng, có vệ sinh tấm pin, có cẩu nâng hạ,
có khung phụ tùng, có kiểm định, có SCADA — mỗi thứ một nhà thầu, một
cam kết, một cách tính tiền. Để người dùng tự gõ tên loại thì ba người
gõ ba kiểu và không báo cáo nào gom được.

Nhưng danh mục KHÔNG đồng nghĩa với "đã làm được"
--------------------------------------------------
Nhiều loại trong danh mục này hiện chỉ là **chỗ để khai**, và một số
loại thì **đã có nơi quản lý riêng** ngoài module này: hợp đồng mua bán
điện nằm ở phần bán điện, hợp đồng EPC và bảo lãnh nằm ở EPCOne, hợp
đồng vay nằm ở phần quản lý vay. Những loại đó đánh dấu ``quan_ly_o_day
= False`` và **không chọn được** khi lập hợp đồng O&M — kèm câu chỉ
đường sang đúng chỗ.

Có danh mục mà không nói rõ chỗ nào làm được chỗ nào chưa thì người xem
đếm số dòng rồi tưởng phần mềm làm hết — đúng cái bẫy đã gặp ở nơi khác.

Nguồn
-----
Danh mục dựng theo tài liệu *"AMI — Danh mục loại hợp đồng trong giai
đoạn O&M"* bản 0.1 ngày 23/10/2026. Tài liệu ghi rõ đây là **đề xuất để
khảo sát và thiết kế**, không phải danh sách hợp đồng đã xác minh của
khách và cũng không phải danh mục bắt buộc theo pháp luật. Phạm vi thật
phải đối chiếu với hợp đồng và phụ lục của từng nhà máy.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

NHOM = [
    ('om', 'Vận hành & bảo trì cốt lõi'),
    ('gio', 'Chuyên biệt điện gió'),
    ('mat_troi', 'Chuyên biệt điện mặt trời'),
    ('vat_tu', 'Vật tư, kiểm định & hạ tầng hỗ trợ'),
    ('thuong_mai', 'Thương mại & tài sản'),
]

AP_DUNG = [
    ('ca_hai', 'Cả hai'),
    ('gio', 'Điện gió'),
    ('mat_troi', 'Điện mặt trời'),
]


class EamOmContractType(models.Model):
    _name = 'eam.om.contract.type'
    _description = 'Loại hợp đồng giai đoạn O&M'
    _order = 'nhom, code'
    _rec_name = 'display_name'

    code = fields.Char(string='Mã', required=True, index=True)
    name = fields.Char(string='Loại hợp đồng', required=True)
    nhom = fields.Selection(NHOM, string='Nhóm', required=True, default='om')
    ap_dung = fields.Selection(
        AP_DUNG, string='Áp dụng cho', required=True, default='ca_hai')
    noi_dung = fields.Text(
        string='Nội dung quản lý chính',
        help='Những thứ hợp đồng loại này phải theo dõi được. Dùng làm '
             'danh sách kiểm khi khảo sát, không phải điều khoản.')

    quan_ly_o_day = fields.Boolean(
        string='Quản lý tại module này', default=True,
        help='Tắt khi loại hợp đồng đã có nơi quản lý riêng. Loại đó vẫn '
             'nằm trong danh mục để thấy bức tranh đủ, nhưng không chọn '
             'được khi lập hợp đồng O&M.')
    quan_ly_o_dau = fields.Char(
        string='Quản lý ở đâu',
        help='Chỉ đường khi loại này không quản lý ở module O&M.')

    uu_tien_demo = fields.Integer(
        string='Thứ tự ưu tiên demo', aggregator=False,
        help='Theo mục "Phạm vi ưu tiên phát triển và demo" của tài liệu '
             'danh mục. 0 là chưa xếp.')
    contract_count = fields.Integer(
        string='Số hợp đồng', compute='_compute_contract_count')
    active = fields.Boolean(default=True)
    note = fields.Text(string='Ghi chú')

    _uniq_code = models.Constraint(
        'UNIQUE(code)', 'Mã loại hợp đồng không được trùng.')

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '%s — %s' % (rec.code or '', rec.name or '')

    def _compute_contract_count(self):
        gom = self.env['eam.om.contract']._read_group(
            [('loai_id', 'in', self.ids)], ['loai_id'], ['__count'])
        dem = {t.id: n for t, n in gom}
        for rec in self:
            rec.contract_count = dem.get(rec.id, 0)

    @api.constrains('quan_ly_o_day', 'quan_ly_o_dau')
    def _check_chi_duong(self):
        for rec in self:
            if not rec.quan_ly_o_day and not (rec.quan_ly_o_dau or '').strip():
                raise ValidationError(_(
                    'Loại "%s" đánh dấu không quản lý ở đây thì phải ghi rõ '
                    'quản lý ở đâu. Để trống là người dùng gặp một loại '
                    'không chọn được mà không biết phải đi đâu.', rec.code))
