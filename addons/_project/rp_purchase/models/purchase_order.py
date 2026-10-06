# -*- coding: utf-8 -*-
"""Hai trục mà đơn mua của Odoo thiếu: dự án và nhóm chi phí.

Nhóm chi phí đặt ở DÒNG chứ không ở đầu đơn — một đơn mua bảo hiểm có
thể gồm cả bảo hiểm công trình lẫn bảo hiểm trách nhiệm, hai nhóm khác
nhau. Ép một nhóm cho cả đơn thì người dùng sẽ chọn bừa, và số liệu
nhóm chi phí thành vô nghĩa.

Dự án thì ngược lại: đặt ở ĐẦU ĐƠN, vì một đơn mua không bao giờ chia
cho hai dự án — chia thì đó là hai đơn.
"""
from odoo import api, fields, models


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    rp_project_id = fields.Many2one(
        're.project', string='Dự án', index=True, tracking=True,
        help='Dự án mà khoản mua này thuộc về. Để trống nghĩa là chi phí '
             'chung của công ty, không vào ngân sách dự án nào.')

    @api.onchange('rp_project_id')
    def _onchange_rp_project(self):
        # Đổi dự án thì nhóm chi phí cũ hết hợp lệ: cây nhóm chi phí là
        # của TỪNG dự án, không dùng chung.
        for l in self.order_line:
            if l.rp_cost_category_id.project_id != self.rp_project_id:
                l.rp_cost_category_id = False


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    rp_project_id = fields.Many2one(
        're.project', related='order_id.rp_project_id', store=True,
        string='Dự án', readonly=True)
    rp_cost_category_id = fields.Many2one(
        'rp.cost.category', string='Nhóm chi phí', index=True,
        domain="[('project_id', '=', rp_project_id)]",
        help='Nhóm chi phí của dự án mà dòng này rơi vào — để đối chiếu '
             'với dự toán cùng nhóm.')
