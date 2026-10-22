# -*- coding: utf-8 -*-
"""Tỷ số hiệu suất và khả dụng ngày — điện mặt trời (IEC 61724-1).

Công thức
---------
::

    E danh định   = tổng xạ × diện tích mô-đun
    Ft            = 1 + hệ số nhiệt × (nhiệt độ mô-đun − nhiệt độ tham chiếu)
    Mẫu số PR     = tổng xạ × diện tích dùng cho PR × hiệu suất × Ft
    PR            = điện năng AC ÷ mẫu số

Vì sao mẫu số có ô GHI ĐÈ
--------------------------
Đã đối chiếu với báo cáo thật của một nhà máy đang vận hành. Hai phần
khớp chính xác: ``E danh định = tổng xạ × diện tích``, và
``PR = AC ÷ mẫu số`` ra đúng 77,34%. Nhưng mẫu số của họ cao hơn công
thức trên **2,53%**, và Ft của họ ứng với nhiệt độ tham chiếu ~26,1 °C
chứ không phải 25 °C.

Hai chênh lệch đó có giả thuyết hợp lý — diện tích phủ bì thay vì diện
tích hứng nắng, và mốc nhiệt độ theo hợp đồng — nhưng **chưa xác nhận**.
Nên ô ghi đè tồn tại để nhà máy nhập đúng mẫu số của họ, và cờ lệch cho
thấy khoảng cách thay vì giấu nó đi. Tính ra một con số PR trông hợp lý
mà sai mẫu số thì không ai phát hiện được.

Khả dụng (PA) không tự suy
---------------------------
PA là tỷ lệ thời gian nhà máy sẵn sàng phát. Nó phải đến từ sổ giờ dừng
máy, mà sổ đó thuộc phần khác. Ở đây để nhập, và sẽ nối tự động khi
module sổ giờ xong — chứ không bịa một công thức tạm.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class EamSolarKpi(models.Model):
    _name = 'eam.solar.kpi'
    _description = 'Hiệu suất ngày — điện mặt trời'
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
    company_id = fields.Many2one(related='plant_id.company_id', store=True)

    weather_id = fields.Many2one(
        'eam.solar.weather', string='Khí tượng ngày',
        compute='_compute_weather', store=True,
        help='Tự nối với bản ghi khí tượng cùng nhà máy, cùng ngày.')

    # ----- Đầu vào -------------------------------------------------------
    energy_ac = fields.Float(
        string='Điện năng AC (kWh)', digits=(16, 1), tracking=True,
        help='Sản lượng xoay chiều dùng làm TỬ SỐ. Sẽ do chuỗi điểm đo '
             'điền tự động khi module đó xong.')
    irradiation = fields.Float(
        string='Tổng xạ (kWh/m²)', related='weather_id.irradiation',
        store=True, readonly=True)
    temp_module = fields.Float(
        string='Nhiệt độ mô-đun (°C)', related='weather_id.temp_module',
        store=True, readonly=True)

    # ----- Hằng số chụp lại tại thời điểm tính ---------------------------
    module_area = fields.Float(
        string='Diện tích mô-đun (m²)', digits=(16, 1), readonly=True)
    area_pr = fields.Float(
        string='Diện tích dùng cho PR (m²)', digits=(16, 1), readonly=True)
    module_eff = fields.Float(
        string='Hiệu suất mô-đun (%)', digits=(5, 2), readonly=True)
    tk_pmpp = fields.Float(
        string='Hệ số nhiệt (/°C)', digits=(6, 4), readonly=True)
    temp_ref = fields.Float(
        string='Nhiệt độ tham chiếu (°C)', digits=(5, 2), readonly=True)

    # ----- Kết quả -------------------------------------------------------
    e_nominal = fields.Float(
        string='E danh định (kWh)', digits=(16, 1),
        compute='_compute_kpi', store=True,
        help='Năng lượng mặt trời tới mặt mô-đun: tổng xạ × diện tích.')
    ft = fields.Float(
        string='Hệ số hiệu chỉnh nhiệt', digits=(6, 4),
        compute='_compute_kpi', store=True)
    pr_denominator = fields.Float(
        string='Mẫu số PR (kWh)', digits=(16, 1),
        compute='_compute_kpi', store=True)
    pr_denominator_manual = fields.Float(
        string='Mẫu số PR — ghi đè (kWh)', digits=(16, 1), tracking=True,
        help='Để trống thì dùng mẫu số tính ra. Khai vào khi nhà máy có '
             'cách dựng mẫu số riêng theo hợp đồng.')
    pr_denominator_used = fields.Float(
        string='Mẫu số đang dùng (kWh)', digits=(16, 1),
        compute='_compute_kpi', store=True)
    lech_mau_so = fields.Float(
        string='Lệch mẫu số (%)', digits=(6, 2),
        compute='_compute_kpi', store=True,
        help='Khoảng cách giữa mẫu số ghi đè và mẫu số tính ra. Khác 0 là '
             'có chỗ ta chưa hiểu đúng công thức của nhà máy.')

    pr = fields.Float(
        string='PR (%)', digits=(6, 2), compute='_compute_kpi', store=True,
        tracking=True)
    pr_guaranteed = fields.Float(
        string='PR cam kết (%)', digits=(5, 2),
        related='plant_id.pv_pr_guaranteed', store=True, readonly=True)
    dat_cam_ket = fields.Boolean(
        string='Đạt cam kết', compute='_compute_kpi', store=True)

    pa = fields.Float(
        string='PA — khả dụng (%)', digits=(6, 2), tracking=True,
        help='Tỷ lệ thời gian nhà máy sẵn sàng phát. Nhập tay cho tới khi '
             'sổ giờ dừng máy nối vào.')

    _uniq_ngay = models.Constraint(
        'UNIQUE(plant_id, date)',
        'Mỗi nhà máy chỉ có một bản ghi hiệu suất cho một ngày.')

    @api.depends('plant_id', 'date')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '%s — %s' % (rec.plant_id.name or '',
                                            rec.date or '')

    @api.depends('plant_id', 'date')
    def _compute_weather(self):
        W = self.env['eam.solar.weather']
        for rec in self:
            rec.weather_id = W.search(
                [('plant_id', '=', rec.plant_id.id),
                 ('date', '=', rec.date)], limit=1) if rec.plant_id and rec.date else False

    @api.depends('energy_ac', 'irradiation', 'temp_module', 'module_area',
                 'area_pr', 'module_eff', 'tk_pmpp', 'temp_ref',
                 'pr_denominator_manual', 'pr_guaranteed')
    def _compute_kpi(self):
        for rec in self:
            dt = rec.area_pr or rec.module_area
            rec.e_nominal = (rec.irradiation or 0) * (rec.module_area or 0)
            rec.ft = (1 + (rec.tk_pmpp or 0)
                      * ((rec.temp_module or 0) - (rec.temp_ref or 0))
                      ) if rec.temp_module else 0.0
            rec.pr_denominator = ((rec.irradiation or 0) * dt
                                  * (rec.module_eff or 0) / 100.0
                                  * (rec.ft or 1))
            rec.pr_denominator_used = (rec.pr_denominator_manual
                                       or rec.pr_denominator)
            rec.lech_mau_so = (
                100.0 * (rec.pr_denominator_manual - rec.pr_denominator)
                / rec.pr_denominator
                if rec.pr_denominator_manual and rec.pr_denominator else 0.0)
            rec.pr = (100.0 * rec.energy_ac / rec.pr_denominator_used
                      if rec.pr_denominator_used else 0.0)
            rec.dat_cam_ket = bool(rec.pr_guaranteed) and rec.pr >= rec.pr_guaranteed

    @api.onchange('plant_id')
    def _onchange_plant(self):
        """Chụp hằng số của nhà máy vào bản ghi.

        Chụp chứ không tham chiếu: sửa hằng số của nhà máy hôm nay KHÔNG
        được làm đổi KPI đã tính của tháng trước.
        """
        for rec in self:
            p = rec.plant_id
            rec.module_area = p.pv_module_area
            rec.area_pr = p.pv_area_pr or p.pv_module_area
            rec.module_eff = p.pv_module_eff
            rec.tk_pmpp = p.pv_tk_pmpp
            rec.temp_ref = p.pv_temp_ref

    @api.model_create_multi
    def create(self, vals_list):
        L = self.env['eam.location']
        for vals in vals_list:
            if vals.get('plant_id') and not vals.get('module_area'):
                p = L.browse(vals['plant_id'])
                vals.setdefault('module_area', p.pv_module_area)
                vals.setdefault('area_pr', p.pv_area_pr or p.pv_module_area)
                vals.setdefault('module_eff', p.pv_module_eff)
                vals.setdefault('tk_pmpp', p.pv_tk_pmpp)
                vals.setdefault('temp_ref', p.pv_temp_ref)
        return super().create(vals_list)

    @api.constrains('pa', 'pr')
    def _check_pct(self):
        for rec in self:
            if rec.pa and not (0 <= rec.pa <= 100):
                raise ValidationError(_('Khả dụng phải nằm trong 0–100%%, '
                                        'đang nhận %s.', rec.pa))
