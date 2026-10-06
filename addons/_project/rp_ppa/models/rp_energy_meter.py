# -*- coding: utf-8 -*-
"""Điểm giao nhận và công-tơ.

Điểm giao nhận quyết định ai chịu tổn thất đường dây: AMI phát ở Lào và
bán TẠI BIÊN GIỚI, nên tổn thất trên đoạn 220kV tới biên giới là của
AMI, còn từ biên giới trở đi là của bên mua. Ghi sai điểm giao là ghi
sai tiền ngay từ con số đầu tiên.

Công-tơ đối chứng (check meter) để riêng vì đối soát hai số là việc có
thật hằng tháng: số của mình và số của bên mua lệch nhau thì phải có
chỗ ghi cả hai.
"""
from odoo import fields, models


class RpEnergyMeter(models.Model):
    _name = 'rp.energy.meter'
    _description = 'Điểm giao nhận / công-tơ'
    _order = 'project_id, sequence, id'

    name = fields.Char(string='Tên điểm đo', required=True)
    code = fields.Char(string='Mã')
    sequence = fields.Integer(default=10)
    project_id = fields.Many2one(
        're.project', string='Dự án', required=True, index=True,
        ondelete='cascade')
    point_type = fields.Selection(
        [('delivery', 'Điểm giao nhận (thanh toán)'),
         ('generation', 'Đầu cực máy phát'),
         ('check', 'Công-tơ đối chứng')],
        string='Loại điểm', required=True, default='delivery')
    serial = fields.Char(string='Số sê-ri công-tơ')
    ct_ratio = fields.Char(string='Tỷ số TI')
    vt_ratio = fields.Char(string='Tỷ số TU')
    loss_factor_percent = fields.Float(
        string='Hệ số tổn thất tới điểm giao (%)', digits=(6, 3),
        help='Tổn thất đường dây từ đầu cực máy phát tới điểm giao nhận. '
             'Bên bán chịu phần này.')
    note = fields.Char(string='Ghi chú')
    active = fields.Boolean(default=True)
