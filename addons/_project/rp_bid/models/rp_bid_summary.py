# -*- coding: utf-8 -*-
"""Tổng hợp vật tư của hồ sơ dự thầu (việc 1411).

Gom MỌI dòng chi phí của các BoQ nhà thầu theo tài nguyên: cần bao nhiêu
xi măng, bao nhiêu công nhân công, bao nhiêu ca máy cho cả gói. Số
lượng là `rp.bid.resource.line.resource_qty` = khối lượng đầu việc ×
định mức, cộng lại.

VẬT TƯ BÊN MỜI THẦU CẤP VẪN HIỆN, TÁCH DÒNG RIÊNG. Phần đó không vào giá
chào, nhưng vẫn phải biết số lượng — để đối chiếu với lượng bên mời thầu
sẽ giao, và vì thiếu thì ta vẫn là người dừng thi công.

DÒNG KHAI THEO % ("vật liệu khác 2%") KHÔNG CÓ SỐ LƯỢNG nên không vào
bảng này — cộng "2" với "1.250 kg xi măng" là vô nghĩa.

SỐ LƯỢNG CHỈ ĐÚNG KHI ĐVT CỦA DÒNG BoQ KHỚP ĐVT CỦA ĐỊNH MỨC. Dòng nào
lệch thì cột "Có dòng lệch ĐVT" bật — số lượng của tài nguyên đó đang
cộng cả phần nhân sai đơn vị, phải rà trước khi đem đi đặt hàng.
"""
from odoo import fields, models, tools

from .rp_bid_boq_line import SUPPLIED_BY


class RpBidMaterialSummary(models.Model):
    _name = 'rp.bid.material.summary'
    _description = 'Tổng hợp vật tư của hồ sơ dự thầu'
    _auto = False
    _order = 'bid_id, resource_type, resource_id, supplied_by'

    bid_id = fields.Many2one('rp.bid', string='Hồ sơ dự thầu', readonly=True)
    resource_id = fields.Many2one(
        'rp.resource', string='Tài nguyên', readonly=True)
    # Cột thật của view (không related) để sắp và nhóm được theo loại.
    resource_type = fields.Selection(
        selection=lambda s: s.env['rp.resource']._fields[
            'resource_type'].selection,
        string='Loại', readonly=True)
    categ_id = fields.Many2one(
        'rp.resource.category', string='Nhóm', readonly=True)
    uom_id = fields.Many2one('uom.uom', string='ĐVT', readonly=True)
    supplied_by = fields.Selection(
        SUPPLIED_BY, string='Ai cấp', readonly=True)
    currency_id = fields.Many2one(related='bid_id.currency_id')
    quantity = fields.Float(
        string='Số lượng', digits=(16, 4), readonly=True,
        help='= Σ (khối lượng đầu việc × định mức) của mọi dòng chi phí '
             'dùng tài nguyên này.')
    amount = fields.Monetary(
        string='Thành tiền', currency_field='currency_id', readonly=True,
        help='= Σ thành tiền các dòng chi phí. Với vật tư bên mời thầu cấp, '
             'đây là giá trị để theo dõi — không vào giá chào.')
    line_count = fields.Integer(
        string='Số đầu việc', readonly=True,
        help='Số dòng BoQ dùng tài nguyên này.')
    uom_mismatch = fields.Boolean(
        string='Có dòng lệch ĐVT', readonly=True,
        help='Ít nhất một dòng BoQ dùng tài nguyên này có ĐVT khác ĐVT của '
             'định mức — số lượng chưa tin được, rà lại các dòng đó.')

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW rp_bid_material_summary AS (
                SELECT min(rl.id)                    AS id,
                       rl.bid_id                     AS bid_id,
                       rl.resource_id                AS resource_id,
                       r.resource_type               AS resource_type,
                       r.categ_id                    AS categ_id,
                       r.uom_id                      AS uom_id,
                       bl.supplied_by                AS supplied_by,
                       sum(rl.resource_qty)          AS quantity,
                       sum(rl.amount)                AS amount,
                       count(DISTINCT rl.line_id)    AS line_count,
                       bool_or(coalesce(bl.uom_mismatch, false))
                                                     AS uom_mismatch
                  FROM rp_bid_resource_line rl
                  JOIN rp_bid_boq_line bl ON bl.id = rl.line_id
                  JOIN rp_resource r ON r.id = rl.resource_id
                 WHERE NOT coalesce(rl.is_percent, false)
              GROUP BY rl.bid_id, rl.resource_id, r.resource_type,
                       r.categ_id, r.uom_id, bl.supplied_by
            )
        """)


class RpBidSummaryOnBid(models.Model):
    _inherit = 'rp.bid'

    material_summary_ids = fields.One2many(
        'rp.bid.material.summary', 'bid_id', string='Tổng hợp vật tư',
        readonly=True)
