# -*- coding: utf-8 -*-
"""Nối biên bản nghiệm thu với phiếu nhập kho — nối, KHÔNG gộp."""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class RpGoodsReceipt(models.Model):
    _inherit = 'rp.goods.receipt'

    picking_ids = fields.Many2many(
        'stock.picking', string='Phiếu nhập kho',
        domain="[('purchase_id', '=', purchase_order_id)]",
        help='Những phiếu nhập kho mà biên bản này nghiệm thu. Dịch vụ '
             'thì để trống — dịch vụ không nhập kho được nhưng vẫn phải '
             'nghiệm thu mới trả tiền.')
    picking_count = fields.Integer(compute='_compute_picking_count')

    @api.depends('picking_ids')
    def _compute_picking_count(self):
        for r in self:
            r.picking_count = len(r.picking_ids)

    def action_mo_phieu_nhap(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': _('Phiếu nhập kho'),
            'res_model': 'stock.picking', 'view_mode': 'list,form',
            'domain': [('id', 'in', self.picking_ids.ids)],
        }


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    rp_receipt_ids = fields.Many2many(
        'rp.goods.receipt', string='Biên bản nghiệm thu')
    rp_receipt_count = fields.Integer(compute='_compute_rp_receipt_count')

    @api.depends('rp_receipt_ids')
    def _compute_rp_receipt_count(self):
        for p in self:
            p.rp_receipt_count = len(p.rp_receipt_ids)

    def action_rp_mo_nghiem_thu(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Biên bản nghiệm thu — %s', self.name),
            'res_model': 'rp.goods.receipt', 'view_mode': 'list,form',
            'domain': [('id', 'in', self.rp_receipt_ids.ids)],
        }

    def action_rp_lap_nghiem_thu(self):
        """Lập biên bản nghiệm thu từ phiếu nhập đã hoàn tất.

        Chỉ lập từ phiếu ĐÃ XONG: biên bản nghiệm thu là căn cứ trả
        tiền, mà hàng chưa vào kho thì chưa có gì để kiểm.
        """
        self.ensure_one()
        if self.state != 'done':
            raise UserError(_(
                'Phiếu nhập "%s" chưa hoàn tất. Biên bản nghiệm thu là '
                'căn cứ trả tiền — hàng chưa vào kho thì chưa có gì để '
                'kiểm.', self.name))
        if not self.purchase_id:
            raise UserError(_(
                'Phiếu nhập này không gắn đơn mua nào, không biết nghiệm '
                'thu theo hợp đồng nào.'))
        bb = self.env['rp.goods.receipt'].create({
            'purchase_order_id': self.purchase_id.id,
            'receipt_type': 'goods',
            'location': self.location_dest_id.complete_name,
            'picking_ids': [(6, 0, self.ids)],
            'line_ids': [(0, 0, {
                'po_line_id': m.purchase_line_id.id,
                'name': m.product_id.display_name,
                'quantity_ordered': m.purchase_line_id.product_qty,
                'quantity_received': m.quantity,
                'quantity_accepted': m.quantity,
                'price_unit': m.purchase_line_id.price_unit,
            }) for m in self.move_ids if m.purchase_line_id],
        })
        self.rp_receipt_ids = [(4, bb.id)]
        return {
            'type': 'ir.actions.act_window',
            'name': _('Biên bản nghiệm thu'),
            'res_model': 'rp.goods.receipt', 'res_id': bb.id,
            'view_mode': 'form',
        }
