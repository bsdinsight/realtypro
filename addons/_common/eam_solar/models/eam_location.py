# -*- coding: utf-8 -*-
"""Hằng số và cấu hình hiệu suất của nhà máy điện mặt trời.

Vì sao nằm trên VỊ TRÍ chứ không phải một bảng riêng
-----------------------------------------------------
EAMOne đã có khái niệm nhà máy: một ``eam.location`` mang
``location_type = 'plant'``, và mọi tài sản đều suy ngược lên được qua
``plant_id``. Dựng thêm một bảng "nhà máy điện mặt trời" là có hai nơi
cùng nói về một thứ, rồi phải đồng bộ hai nơi đó mãi mãi.

Vì sao công thức phải khai được
--------------------------------
Tỷ số hiệu suất (PR) trông như một công thức cố định, nhưng ba thứ trong
nó thay đổi theo từng nhà máy: lấy bức xạ từ cảm biến nào, mấy cảm biến
thì lấy trung bình, và hệ số hiệu chỉnh nhiệt đặt ở đâu trong công thức.
Viết cứng một cách tính là đúng cho nhà máy đầu tiên và sai cho mọi nhà
máy sau — mà cái sai đó hiện lên màn hình y hệt cái đúng.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class EamLocation(models.Model):
    _inherit = 'eam.location'

    is_solar = fields.Boolean(
        string='Nhà máy điện mặt trời',
        help='Bật cho vị trí cấp nhà máy để mở phần hằng số và hiệu suất '
             'quang điện.')

    # ----- Hằng số nhà máy (SITE CONSTANTS) ------------------------------
    pv_module_area = fields.Float(
        string='Diện tích mô-đun (m²)', digits=(16, 1),
        help='Tổng diện tích mặt hứng nắng của toàn bộ tấm pin.')
    pv_module_eff = fields.Float(
        string='Hiệu suất mô-đun (%)', digits=(5, 2),
        help='Hiệu suất danh định của tấm pin ở điều kiện chuẩn.')
    pv_planned_temp = fields.Float(
        string='Nhiệt độ thiết kế (°C)', digits=(5, 1),
        help='Nhiệt độ môi trường dùng làm mốc khi hiệu chỉnh nhiệt.')
    pv_tk_pmpp = fields.Float(
        string='Hệ số nhiệt TKPMPP (/°C)', digits=(6, 4),
        help='Hệ số nhiệt của điểm công suất cực đại — thông số của tấm '
             'pin, thường âm (ví dụ −0,004 nghĩa là mất 0,4% công suất '
             'cho mỗi độ nóng thêm).')
    pv_area_pr = fields.Float(
        string='Diện tích dùng cho PR (m²)', digits=(16, 1),
        help='Để trống thì lấy bằng diện tích mô-đun ở trên. Khai riêng '
             'khi hợp đồng dùng DIỆN TÍCH PHỦ BÌ (tính cả khung) cho mẫu '
             'số tỷ số hiệu suất — chênh 2–3% so với diện tích hứng nắng, '
             'và chênh đó đi thẳng vào KPI.')
    pv_temp_ref = fields.Float(
        string='Nhiệt độ tham chiếu (°C)', digits=(5, 2), default=25.0,
        help='Mốc để hiệu chỉnh nhiệt. Chuẩn STC là 25 °C, nhưng hợp đồng '
             'có thể chốt mức khác — khai đúng mức của hợp đồng.')
    pv_pr_guaranteed = fields.Float(
        string='PR cam kết (%)', digits=(5, 2),
        help='Mức tỷ số hiệu suất nhà thầu cam kết trong hợp đồng. '
             'Dùng để so sánh, và là căn cứ phạt nếu không đạt.')

    # ----- Cách lấy bức xạ -----------------------------------------------
    pv_irr_mode = fields.Selection(
        [('avg', 'Trung bình tất cả cảm biến đã chọn'),
         ('first', 'Chỉ dùng cảm biến chính')],
        string='Cách lấy bức xạ', default='avg',
        help='Nhà máy có 2–3 cảm biến bức xạ thì lấy trung bình hay chỉ '
             'dùng một cái — khách quyết, không phải phần mềm quyết.')
    pv_irr_tag_ids = fields.Many2many(
        'eam.tag', 'eam_location_irr_tag_rel', 'location_id', 'tag_id',
        string='Cảm biến bức xạ',
        help='Thứ tự có nghĩa khi chọn "chỉ dùng cảm biến chính": cái '
             'đầu tiên là cái chính.')
    pv_irr_tag_count = fields.Integer(
        string='Số cảm biến bức xạ', compute='_compute_pv_irr_count')

    weather_ids = fields.One2many(
        'eam.solar.weather', 'plant_id', string='Nhật ký khí tượng')
    weather_count = fields.Integer(
        string='Số ngày khí tượng', compute='_compute_pv_irr_count')

    @api.depends('pv_irr_tag_ids', 'weather_ids')
    def _compute_pv_irr_count(self):
        for rec in self:
            rec.pv_irr_tag_count = len(rec.pv_irr_tag_ids)
            rec.weather_count = len(rec.weather_ids)

    @api.constrains('is_solar', 'location_type')
    def _check_is_solar(self):
        for rec in self:
            if rec.is_solar and rec.location_type != 'plant':
                raise ValidationError(_(
                    'Chỉ bật "Nhà máy điện mặt trời" cho vị trí cấp NHÀ '
                    'MÁY. "%s" đang là %s.',
                    rec.complete_name,
                    dict(rec._fields['location_type'].selection
                         ).get(rec.location_type)))

    @api.constrains('pv_module_eff')
    def _check_module_eff(self):
        for rec in self:
            if rec.pv_module_eff and not (1 <= rec.pv_module_eff <= 50):
                raise ValidationError(_(
                    'Hiệu suất mô-đun phải khai theo PHẦN TRĂM (ví dụ 17,4 '
                    'chứ không phải 0,174). Đang nhận: %s.',
                    rec.pv_module_eff))

    def action_xem_khi_tuong(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Khí tượng — %s', self.name),
            'res_model': 'eam.solar.weather',
            'view_mode': 'list,form',
            'domain': [('plant_id', '=', self.id)],
            'context': {'default_plant_id': self.id},
        }
