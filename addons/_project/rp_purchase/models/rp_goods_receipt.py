# -*- coding: utf-8 -*-
"""Biên bản giao nhận & nghiệm thu hàng hoá — dịch vụ.

KHÔNG dùng phiếu nhập kho của phân hệ Kho, vì phần lớn thứ chủ đầu tư
mua là DỊCH VỤ: tư vấn giám sát, bảo hiểm, kiểm định, đào tạo. Dịch vụ
không nhập kho được nhưng vẫn phải nghiệm thu, và vẫn phải có biên bản
trước khi trả tiền. Một biên bản dùng chung cho cả hàng lẫn dịch vụ thì
quy trình thanh toán chỉ có một cửa.

Tách số LƯỢNG NHẬN khỏi số LƯỢNG NGHIỆM THU: nhận đủ mà kiểm tra không
đạt là chuyện thường, và phần không đạt thì không được trả tiền. Gộp
một cột là mất đúng chỗ tranh chấp hay xảy ra nhất.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class RpGoodsReceipt(models.Model):
    _name = 'rp.goods.receipt'
    _description = 'Biên bản giao nhận & nghiệm thu'
    _inherit = ['mail.thread']
    _order = 'date desc, id desc'

    name = fields.Char(string='Số biên bản', required=True, copy=False,
                       default=lambda self: _('Mới'), tracking=True)
    purchase_order_id = fields.Many2one(
        'purchase.order', string='Đơn mua', required=True, index=True,
        ondelete='restrict', tracking=True)
    partner_id = fields.Many2one(
        'res.partner', related='purchase_order_id.partner_id', store=True,
        string='Nhà cung cấp', readonly=True)
    project_id = fields.Many2one(
        're.project', related='purchase_order_id.rp_project_id',
        store=True, string='Dự án', readonly=True)
    date = fields.Date(string='Ngày nghiệm thu', required=True,
                       default=fields.Date.context_today, tracking=True)
    receipt_type = fields.Selection(
        [('goods', 'Hàng hoá'), ('service', 'Dịch vụ')],
        string='Loại', default='goods', required=True)
    location = fields.Char(string='Địa điểm giao nhận')
    inspector_id = fields.Many2one('res.users', string='Người kiểm tra',
                                   default=lambda self: self.env.user)
    representative_supplier = fields.Char(string='Đại diện NCC')
    result = fields.Selection(
        [('pass', 'Đạt'),
         ('conditional', 'Đạt có điều kiện'),
         ('fail', 'Không đạt')],
        string='Kết luận kiểm tra', default='pass', required=True,
        tracking=True)
    remark = fields.Text(string='Tồn tại cần khắc phục')
    state = fields.Selection(
        [('draft', 'Nháp'), ('confirmed', 'Đã xác nhận'),
         ('cancelled', 'Huỷ')],
        string='Trạng thái', default='draft', required=True, tracking=True,
        copy=False)
    line_ids = fields.One2many(
        'rp.goods.receipt.line', 'receipt_id', string='Nội dung')
    amount_accepted = fields.Monetary(
        string='Giá trị nghiệm thu', compute='_compute_tong', store=True,
        currency_field='currency_id')
    payment_request_ids = fields.One2many(
        'rp.payment.request', 'receipt_id', string='Đề nghị thanh toán')
    currency_id = fields.Many2one(
        'res.currency', related='purchase_order_id.currency_id',
        readonly=True)
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company, index=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('Mới')) == _('Mới'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'rp.goods.receipt') or _('BB mới')
        return super().create(vals_list)

    @api.depends('line_ids.amount_accepted')
    def _compute_tong(self):
        for r in self:
            r.amount_accepted = sum(r.line_ids.mapped('amount_accepted'))

    @api.onchange('purchase_order_id')
    def _onchange_po(self):
        """Kéo dòng đơn mua sang để khỏi gõ lại."""
        if not self.purchase_order_id:
            return
        self.line_ids = [(5, 0, 0)] + [(0, 0, {
            'po_line_id': l.id, 'name': l.name,
            'quantity_ordered': l.product_qty,
            'quantity_received': l.product_qty,
            'quantity_accepted': l.product_qty,
            'price_unit': l.price_unit,
        }) for l in self.purchase_order_id.order_line]

    def action_xac_nhan(self):
        for r in self:
            if not r.line_ids:
                raise UserError(_('Biên bản "%s" chưa có nội dung.', r.name))
            if r.result == 'fail':
                raise UserError(_(
                    'Kết luận "Không đạt" thì không xác nhận nghiệm thu '
                    'được — nghiệm thu xong là mở đường trả tiền. Ghi tồn '
                    'tại rồi để nhà cung cấp khắc phục, hoặc chuyển sang '
                    '"Đạt có điều kiện" nếu đã thống nhất xử lý.'))
            r.state = 'confirmed'
        return True

    def action_ve_nhap(self):
        self.write({'state': 'draft'})
        return True


class RpGoodsReceiptLine(models.Model):
    _name = 'rp.goods.receipt.line'
    _description = 'Dòng biên bản nghiệm thu'
    _order = 'receipt_id, id'

    receipt_id = fields.Many2one(
        'rp.goods.receipt', string='Biên bản', required=True, index=True,
        ondelete='cascade')
    po_line_id = fields.Many2one(
        'purchase.order.line', string='Dòng đơn mua', ondelete='restrict')
    name = fields.Char(string='Nội dung', required=True)
    quantity_ordered = fields.Float(string='SL đặt')
    quantity_received = fields.Float(string='SL nhận')
    quantity_accepted = fields.Float(string='SL nghiệm thu')
    quantity_rejected = fields.Float(
        string='SL không đạt', compute='_compute_rejected', store=True)
    price_unit = fields.Monetary(string='Đơn giá',
                                 currency_field='currency_id')
    amount_accepted = fields.Monetary(
        string='Thành tiền nghiệm thu', compute='_compute_rejected',
        store=True, currency_field='currency_id')
    currency_id = fields.Many2one(
        'res.currency', related='receipt_id.currency_id', readonly=True)

    @api.depends('quantity_received', 'quantity_accepted', 'price_unit')
    def _compute_rejected(self):
        for l in self:
            l.quantity_rejected = max(
                0.0, (l.quantity_received or 0.0) - (l.quantity_accepted or 0.0))
            l.amount_accepted = (l.quantity_accepted or 0.0) * (l.price_unit or 0.0)
