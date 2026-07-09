# -*- coding: utf-8 -*-
"""Hồ sơ nhà thầu trên Network (mở rộng res.partner)."""
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    cn_is_contractor = fields.Boolean(string='Là nhà thầu (Network)')
    cn_specialties = fields.Char(
        string='Chuyên môn', help='Vd: Kết cấu, MEP, Hoàn thiện, Nền móng…')
    cn_license = fields.Char(string='Số giấy phép / chứng chỉ')
    cn_service_areas = fields.Char(string='Khu vực hoạt động')
    cn_rating = fields.Float(string='Đánh giá (0–5)')
    cn_verified = fields.Boolean(string='Đã xác minh')
    cn_bid_ids = fields.One2many('cn.bid', 'contractor_id',
                                 string='Hồ sơ dự thầu')
    cn_bid_count = fields.Integer(compute='_compute_cn_bid_count')

    def _compute_cn_bid_count(self):
        data = self.env['cn.bid']._read_group(
            [('contractor_id', 'in', self.ids)], groupby=['contractor_id'],
            aggregates=['__count'])
        mapped = {p.id: c for p, c in data}
        for rec in self:
            rec.cn_bid_count = mapped.get(rec.id, 0)
