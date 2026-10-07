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
    rp_request_id = fields.Many2one(
        'rp.purchase.request', string='Yêu cầu mua', index=True,
        ondelete='set null', tracking=True,
        help='Yêu cầu đã duyệt sinh ra đơn mua này. Một yêu cầu ra được '
             'nhiều đơn vì có thể cần nhiều nhà cung cấp.')
    rp_receipt_ids = fields.One2many(
        'rp.goods.receipt', 'purchase_order_id',
        string='Biên bản nghiệm thu')
    rp_receipt_count = fields.Integer(compute='_compute_rp_receipt')
    rp_payment_request_ids = fields.One2many(
        'rp.payment.request', 'purchase_order_id',
        string='Đề nghị thanh toán')

    def _compute_rp_receipt(self):
        for o in self:
            o.rp_receipt_count = len(o.rp_receipt_ids)

    def action_rp_mo_nghiem_thu(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Nghiệm thu — %s' % self.name,
            'res_model': 'rp.goods.receipt', 'view_mode': 'list,form',
            'domain': [('purchase_order_id', '=', self.id)],
            'context': {'default_purchase_order_id': self.id},
        }

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
