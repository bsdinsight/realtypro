# -*- coding: utf-8 -*-
"""Nhóm báo cáo — bắc cầu giữa 23 loại chuẩn và 6 dòng khách quen đọc.

Vì sao cần một lớp ánh xạ
--------------------------
Chuẩn IEC 61400-26 chia thời gian thành 23 loại, xếp cây và có thứ tự ưu
tiên. Đó là thứ dùng để hạch toán cho đúng. Nhưng tờ báo cáo vận hành
ngày mà khách đọc mỗi sáng chỉ có sáu dòng: lưới ngoài, cắt giảm, bảo
trì theo kế hoạch, sự cố thiết bị, sự cố ngoài phạm vi, nhà thầu O&M.

Ép người vận hành đọc 23 dòng là họ sẽ tự cộng tay ra sáu dòng, và mỗi
người cộng một kiểu. Ép hệ chỉ lưu sáu dòng là mất khả năng truy ngược
và mất luôn cơ chế ưu tiên của chuẩn.

Nên lưu theo **chuẩn**, hiện theo **nhóm** — và phép ánh xạ là dữ liệu,
vì tờ báo cáo của điện gió và điện mặt trời gộp khác nhau.

Loại chưa ánh xạ phải HIỆN RA
------------------------------
Loại thời gian không thuộc nhóm nào thì giờ của nó biến mất khỏi báo
cáo. Tổng sáu dòng khi đó nhỏ hơn tổng thật, mà không dòng nào báo
thiếu. Nên có màn lọc riêng cho loại chưa ánh xạ, và báo cáo cộng thêm
một dòng "chưa xếp nhóm" thay vì bỏ đi.
"""
from odoo import _, api, fields, models


class EamTimeGroup(models.Model):
    _name = 'eam.time.group'
    _description = 'Nhóm thời gian trên báo cáo'
    _order = 'sequence, code'
    _rec_name = 'display_name'

    code = fields.Char(string='Mã', required=True, index=True)
    name = fields.Char(string='Tên nhóm', required=True, translate=True)
    sequence = fields.Integer(default=10)
    mo_ta = fields.Text(string='Gồm những gì')

    la_cat_giam = fields.Boolean(
        string='Là nhóm cắt giảm',
        help='Đánh dấu đúng MỘT nhóm. Giờ cắt giảm bị trừ khi tính giờ '
             'vận hành dùng cho tỷ số hiệu suất — máy vẫn sẵn sàng, chỉ '
             'là lưới không nhận. Không đánh dấu thì hai cách tính giờ '
             'vận hành ra cùng một số, và phần hiệu suất sai theo.')
    tinh_cho_nha_thau = fields.Boolean(
        string='Mặc định tính cho nhà thầu O&M',
        help='Chỉ là GỢI Ý khi người dùng quy trách nhiệm cho từng khoảng '
             'dừng. Quy trách nhiệm thật vẫn nằm ở từng bản ghi, vì cùng '
             'một nhóm có lần do nhà thầu có lần không.')

    category_ids = fields.One2many(
        'eam.time.category', 'group_id', string='Loại thời gian')
    category_count = fields.Integer(
        string='Số loại', compute='_compute_dem')
    active = fields.Boolean(default=True)

    _uniq_code = models.Constraint(
        'UNIQUE(code)', 'Mã nhóm thời gian không được trùng.')

    def _compute_dem(self):
        gom = self.env['eam.time.category']._read_group(
            [('group_id', 'in', self.ids)], ['group_id'], ['__count'])
        dem = {g.id: n for g, n in gom}
        for rec in self:
            rec.category_count = dem.get(rec.id, 0)

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '%s — %s' % (rec.code or '', rec.name or '')


class EamTimeCategory(models.Model):
    _inherit = 'eam.time.category'

    group_id = fields.Many2one(
        'eam.time.group', string='Nhóm trên báo cáo', ondelete='set null',
        index=True,
        help='Để trống thì giờ của loại này rơi vào dòng "chưa xếp nhóm" '
             'trên báo cáo — hiện ra chứ không biến mất.')
