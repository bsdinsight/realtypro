# -*- coding: utf-8 -*-
"""Đường cong công suất cam kết — dữ liệu gốc từ nhà chế tạo.

Đây là thứ **hợp đồng bảo lãnh sản lượng dựa vào**, nên nó là dữ liệu
gốc phải lưu và phải khai rõ nguồn: cam kết trong hợp đồng, hay chỉ là
đường cong thiết kế in trong catalogue, hay đường cong đo được lúc
nghiệm thu. Ba thứ đó khác nhau về giá trị pháp lý, và trộn lẫn thì
lúc đòi bảo hành không ai biết đang so với cái gì.

Mật độ không khí quy chiếu
---------------------------
Đường cong luôn đi kèm một mật độ quy chiếu, gần như luôn là 1,225
kg/m³ (khí quyển chuẩn, mực nước biển, 15 °C). Nhà máy ở cao nguyên
Đắk Lắk cao 600 m thì không khí loãng hơn, cùng tốc độ gió cho ít công
suất hơn — **không phải tua-bin kém**. So thẳng số đo với đường cong mà
không hiệu chỉnh là buộc tội nhà chế tạo một cách oan.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

LOAI_DUONG = [
    ('warranted', 'Cam kết trong hợp đồng'),
    ('design', 'Thiết kế / catalogue'),
    ('measured', 'Đo được khi nghiệm thu'),
]


class EamPowerCurve(models.Model):
    _name = 'eam.power.curve'
    _description = 'Đường cong công suất'
    _inherit = ['mail.thread']
    _order = 'name'

    name = fields.Char(string='Tên đường cong', required=True, tracking=True)
    curve_type = fields.Selection(
        LOAI_DUONG, string='Loại', required=True, default='warranted',
        tracking=True,
        help='Cam kết hợp đồng, thiết kế, hay đo khi nghiệm thu — ba thứ '
             'khác nhau về giá trị pháp lý. Trộn lẫn thì lúc đòi bảo '
             'hành không ai biết đang so với cái gì.')
    model_ref = fields.Char(string='Model tua-bin', tracking=True)
    category_id = fields.Many2one(
        'eam.asset.category', string='Áp cho loại cấu phần',
        ondelete='restrict', index=True)
    rated_kw = fields.Float(string='Công suất định mức (kW)',
                            digits=(16, 1), required=True, tracking=True)
    rotor_d = fields.Float(string='Đường kính rotor (m)', digits=(16, 1))
    air_density_ref = fields.Float(
        string='Mật độ quy chiếu (kg/m³)', digits=(16, 4), default=1.225,
        required=True,
        help='Gần như luôn là 1,225 — khí quyển chuẩn ở mực nước biển, '
             '15 °C. Đường cong không ghi mật độ quy chiếu là đường cong '
             'không dùng để so được.')
    regulation = fields.Selection(
        [('pitch', 'Điều khiển góc cánh (pitch)'),
         ('stall', 'Thất tốc (stall)')],
        string='Kiểu điều khiển', default='pitch', required=True,
        help='Quyết định HIỆU CHỈNH CÁI GÌ theo mật độ không khí. Pitch '
             'thì chuẩn hoá TỐC ĐỘ GIÓ; stall thì chuẩn hoá CÔNG SUẤT. '
             'Làm ngược là sai cả đường cong.')
    point_ids = fields.One2many(
        'eam.power.curve.point', 'curve_id', string='Các điểm')
    point_count = fields.Integer(string='Số điểm', compute='_compute_point')
    note = fields.Text(string='Nguồn & ghi chú')
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', string='Công ty', required=True,
        default=lambda self: self.env.company, index=True)

    @api.depends('point_ids')
    def _compute_point(self):
        for c in self:
            c.point_count = len(c.point_ids)

    @api.depends('name', 'curve_type')
    def _compute_display_name(self):
        nhan = dict(LOAI_DUONG)
        for c in self:
            c.display_name = '%s (%s)' % (c.name or '',
                                          nhan.get(c.curve_type, ''))

    @api.constrains('point_ids')
    def _check_diem(self):
        for c in self:
            if not c.point_ids:
                continue
            vs = c.point_ids.mapped('wind_speed')
            if len(set(vs)) != len(vs):
                raise ValidationError(_(
                    'Đường cong "%s" có hai điểm cùng một tốc độ gió.',
                    c.name))

    def tra_cong_suat(self, v):
        """Công suất cam kết tại tốc độ gió ``v`` — NỘI SUY TUYẾN TÍNH.

        Ngoài dải đã khai thì trả ``None`` chứ không ngoại suy: đường
        cong chỉ có giá trị trong dải nhà chế tạo đã công bố, kéo dài nó
        ra ngoài là tự bịa ra một cam kết mà họ chưa từng đưa.
        """
        self.ensure_one()
        ds = sorted(self.point_ids, key=lambda p: p.wind_speed)
        if not ds:
            return None
        if v < ds[0].wind_speed or v > ds[-1].wind_speed:
            return None
        for a, b in zip(ds, ds[1:]):
            if a.wind_speed <= v <= b.wind_speed:
                if b.wind_speed == a.wind_speed:
                    return a.power_kw
                t = (v - a.wind_speed) / (b.wind_speed - a.wind_speed)
                return a.power_kw + t * (b.power_kw - a.power_kw)
        return ds[-1].power_kw


class EamPowerCurvePoint(models.Model):
    _name = 'eam.power.curve.point'
    _description = 'Điểm trên đường cong công suất'
    _order = 'curve_id, wind_speed'

    curve_id = fields.Many2one(
        'eam.power.curve', string='Đường cong', required=True,
        ondelete='cascade', index=True)
    wind_speed = fields.Float(string='Tốc độ gió (m/s)', digits=(16, 2),
                              required=True)
    power_kw = fields.Float(string='Công suất (kW)', digits=(16, 1),
                            required=True)
    ct = fields.Float(
        string='Hệ số lực đẩy Ct', digits=(16, 3),
        help='Không bắt buộc. Dùng cho tính toán hiệu ứng vệt gió giữa '
             'các trụ — chưa dùng tới ở bản này.')
    company_id = fields.Many2one(
        related='curve_id.company_id', store=True, index=True)

    @api.depends('wind_speed', 'power_kw')
    def _compute_display_name(self):
        for p in self:
            p.display_name = '%.1f m/s → %.0f kW' % (p.wind_speed or 0,
                                                     p.power_kw or 0)
