# -*- coding: utf-8 -*-
"""Chi phí phụ tùng theo nhà máy / tua-bin / cấu phần / lệnh (KHO-37).

Dựng bằng khung nhìn SQL chứ không bằng bảng: số liệu đã nằm hết ở
``stock.move`` và ``eam.work.order`` rồi, chép sang bảng thứ hai là tạo
ra hai nguồn sự thật — và cái thứ hai bao giờ cũng lệch trước.

Chỉ đếm hàng ĐI RA khỏi kho về phía tiêu dùng hoặc thiết bị. Phiếu nhập,
điều chuyển và kiểm kê không phải chi phí bảo trì.
"""
from odoo import fields, models, tools


class EamPartCostReport(models.Model):
    _name = 'eam.part.cost.report'
    _description = 'Chi phí phụ tùng theo chiều'
    _auto = False
    _order = 'date desc'

    date = fields.Date(string='Ngày', readonly=True)
    product_id = fields.Many2one('product.product', string='Vật tư',
                                 readonly=True)
    category_id = fields.Many2one('eam.asset.category',
                                  string='Loại cấu phần', readonly=True)
    work_order_id = fields.Many2one('eam.work.order',
                                    string='Lệnh công việc', readonly=True)
    location_id = fields.Many2one('eam.location', string='Vị trí thiết bị',
                                  readonly=True)
    plant_id = fields.Many2one('eam.location', string='Nhà máy',
                               readonly=True)
    work_type = fields.Char(string='Loại công việc', readonly=True)
    qty = fields.Float(string='Số lượng', readonly=True)
    amount = fields.Monetary(string='Giá trị', readonly=True,
                             currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', string='Tiền tệ',
                                  readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT m.id                         AS id,
                       m.date::date                 AS date,
                       m.product_id                 AS product_id,
                       pt.eam_category_id           AS category_id,
                       m.eam_work_order_id          AS work_order_id,
                       wo.location_id               AS location_id,
                       el.plant_id                  AS plant_id,
                       wo.work_type                 AS work_type,
                       m.quantity                   AS qty,
                       -- Odoo 19 bỏ ir_property: giá vốn phụ thuộc công
                       -- ty nay nằm trong cột jsonb, khoá là id công ty.
                       m.quantity * COALESCE(
                           (pp.standard_price ->> m.company_id::text)
                               ::numeric, 0.0)      AS amount,
                       c.currency_id                AS currency_id
                  FROM stock_move m
                  JOIN product_product pp ON pp.id = m.product_id
                  JOIN product_template pt ON pt.id = pp.product_tmpl_id
                  JOIN stock_location dst ON dst.id = m.location_dest_id
                  LEFT JOIN eam_work_order wo ON wo.id = m.eam_work_order_id
                  LEFT JOIN eam_location el ON el.id = wo.location_id
                  JOIN res_company c ON c.id = m.company_id
                 WHERE m.state = 'done'
                   AND dst.usage = 'production'
            )
        """ % self._table)
