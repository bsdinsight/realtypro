# -*- coding: utf-8 -*-
"""Nhật ký khí tượng ngày của nhà máy điện mặt trời.

Vì sao là một bản ghi mỗi ngày mỗi nhà máy
-------------------------------------------
Báo cáo vận hành ngày có một khối khí tượng, và khối đó trộn hai thứ bản
chất khác nhau: **số đo máy đọc được** (bức xạ, nhiệt độ, tốc độ gió) và
**quan sát của người trực** (trời nắng hay mưa lúc 6h, 9h, 12h, 15h).
Trộn vào một bảng là đúng, vì chúng cùng mô tả một ngày — nhưng phải
tách rõ ô nào máy điền, ô nào người điền, nếu không người trực sẽ gõ đè
lên số đo.

Bức xạ là mẫu số của tỷ số hiệu suất
-------------------------------------
Sai bức xạ thì sai toàn bộ phần hạch toán hiệu suất, mà cái sai đó không
lộ ra ở đâu cả. Nên ô tổng xạ ghi luôn **lấy từ cảm biến nào** — một
dòng chữ, nhưng là dòng chữ cứu được một cuộc tranh cãi.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

#: Quan sát bằng mắt — bốn mốc trong ngày theo mẫu báo cáo của khách.
TROI = [
    ('sunny', 'Nắng'),
    ('partly', 'Nắng gián đoạn'),
    ('cloudy', 'Nhiều mây'),
    ('overcast', 'Âm u'),
    ('rain', 'Mưa'),
    ('storm', 'Giông bão'),
]


class EamSolarWeather(models.Model):
    _name = 'eam.solar.weather'
    _description = 'Khí tượng ngày — điện mặt trời'
    _inherit = ['mail.thread']
    _order = 'date desc, plant_id'
    _rec_name = 'display_name'

    plant_id = fields.Many2one(
        'eam.location', string='Nhà máy', required=True, index=True,
        domain="[('is_solar', '=', True)]", ondelete='cascade',
        tracking=True)
    date = fields.Date(
        string='Ngày', required=True, index=True, tracking=True,
        default=fields.Date.context_today)
    company_id = fields.Many2one(
        related='plant_id.company_id', store=True)

    # ----- Máy đọc được --------------------------------------------------
    irradiance_avg = fields.Float(
        string='Bức xạ trung bình (kW/m²)', digits=(8, 3), tracking=True,
        help='Cường độ bức xạ trung bình trong giờ có nắng.')
    irradiation = fields.Float(
        string='Tổng xạ (kWh/m²)', digits=(8, 3), tracking=True,
        help='Tổng năng lượng mặt trời tới mặt mô-đun trong ngày. Đây là '
             'MẪU SỐ của tỷ số hiệu suất — sai ô này là sai cả phần KPI.')
    irr_source = fields.Char(
        string='Nguồn bức xạ', readonly=True,
        help='Lấy từ cảm biến nào, trung bình mấy cái. Ghi lại để sau này '
             'còn truy được vì sao ra con số đó.')
    temp_ambient = fields.Float(
        string='Nhiệt độ môi trường (°C)', digits=(5, 2))
    temp_module = fields.Float(
        string='Nhiệt độ mô-đun (°C)', digits=(5, 2),
        help='Tấm pin luôn nóng hơn không khí; đây mới là nhiệt độ dùng '
             'để hiệu chỉnh công suất.')
    wind_speed = fields.Float(
        string='Tốc độ gió (m/s)', digits=(5, 2),
        help='Gió làm mát tấm pin nên ảnh hưởng gián tiếp tới sản lượng.')
    sunny_hours = fields.Float(
        string='Số giờ nắng', digits=(5, 2))

    # ----- Người trực quan sát -------------------------------------------
    obs_06 = fields.Selection(TROI, string='Trời lúc 6h')
    obs_09 = fields.Selection(TROI, string='Trời lúc 9h')
    obs_12 = fields.Selection(TROI, string='Trời lúc 12h')
    obs_15 = fields.Selection(TROI, string='Trời lúc 15h')
    obs_note = fields.Char(string='Ghi chú thời tiết')

    nguon = fields.Selection(
        [('may', 'Máy lấy từ số đo'),
         ('tay', 'Người nhập tay'),
         ('tron', 'Máy lấy, người sửa')],
        string='Nguồn số liệu', default='tay', readonly=True, tracking=True,
        help='Người sửa đè lên số máy lấy thì chuyển sang "máy lấy, người '
             'sửa" — để sau còn biết con số nào đã bị can thiệp.')

    _uniq_ngay = models.Constraint(
        'UNIQUE(plant_id, date)',
        'Mỗi nhà máy chỉ có một bản ghi khí tượng cho một ngày.')

    @api.depends('plant_id', 'date')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '%s — %s' % (
                rec.plant_id.name or '', rec.date or '')

    @api.constrains('irradiation', 'irradiance_avg')
    def _check_irr(self):
        for rec in self:
            if rec.irradiation and rec.irradiation > 15:
                raise ValidationError(_(
                    'Tổng xạ %s kWh/m²/ngày là bất thường — mức cao nhất '
                    'ghi nhận trên Trái Đất quanh 9. Kiểm lại đơn vị: có '
                    'thể đang nhập Wh/m² thay vì kWh/m².', rec.irradiation))
            if rec.irradiance_avg and rec.irradiance_avg > 2:
                raise ValidationError(_(
                    'Bức xạ %s kW/m² vượt hằng số mặt trời. Kiểm lại đơn '
                    'vị: có thể đang nhập W/m².', rec.irradiance_avg))

    def write(self, vals):
        """Người sửa đè lên số máy lấy thì đánh dấu lại."""
        o_may = {'irradiance_avg', 'irradiation', 'temp_ambient',
                 'temp_module', 'wind_speed', 'sunny_hours'}
        if o_may & set(vals) and not self.env.context.get('tu_so_do'):
            for rec in self:
                if rec.nguon == 'may':
                    vals = dict(vals, nguon='tron')
                    break
        return super().write(vals)
