# -*- coding: utf-8 -*-
"""Giấy đề nghị thanh toán — cửa duy nhất để tiền đi ra.

Ở Việt Nam đây là chứng từ thật và là chỗ kiểm soát mạnh nhất: không có
đề nghị thanh toán được duyệt thì kế toán không chi. Nó gom đủ bộ hồ sơ
— đơn mua, biên bản nghiệm thu, hoá đơn — để người duyệt nhìn một chỗ
mà quyết, thay vì lục ba màn khác nhau.

Số tiền đề nghị mặc định lấy theo GIÁ TRỊ NGHIỆM THU chứ không theo giá
trị đơn mua: phần hàng không đạt thì không được trả, và đó chính là lý
do biên bản tách riêng số lượng nhận với số lượng nghiệm thu.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class RpPaymentRequest(models.Model):
    _name = 'rp.payment.request'
    _description = 'Giấy đề nghị thanh toán'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(string='Số đề nghị', required=True, copy=False,
                       default=lambda self: _('Mới'), tracking=True)
    project_id = fields.Many2one(
        're.project', string='Dự án', index=True, ondelete='restrict')
    partner_id = fields.Many2one(
        'res.partner', string='Đơn vị thụ hưởng', required=True,
        ondelete='restrict', tracking=True)
    purchase_order_id = fields.Many2one(
        'purchase.order', string='Đơn mua', ondelete='restrict',
        tracking=True)
    receipt_id = fields.Many2one(
        'rp.goods.receipt', string='Biên bản nghiệm thu',
        domain="[('purchase_order_id', '=', purchase_order_id),"
               " ('state', '=', 'confirmed')]",
        ondelete='restrict', tracking=True)
    invoice_id = fields.Many2one(
        'account.move', string='Hoá đơn',
        domain="[('move_type', 'in', ('in_invoice', 'in_refund'))]",
        ondelete='restrict', tracking=True)
    date = fields.Date(string='Ngày đề nghị', required=True,
                       default=fields.Date.context_today, tracking=True)
    date_due = fields.Date(string='Đề nghị chi trước ngày', tracking=True)
    amount = fields.Monetary(string='Số tiền đề nghị', required=True,
                             currency_field='currency_id', tracking=True)
    reason = fields.Text(string='Nội dung thanh toán', required=True)
    requester_id = fields.Many2one(
        'res.users', string='Người đề nghị', required=True,
        default=lambda self: self.env.user)
    approver_id = fields.Many2one('res.users', string='Người duyệt',
                                  readonly=True, tracking=True)
    state = fields.Selection(
        [('draft', 'Nháp'),
         ('to_approve', 'Chờ duyệt'),
         ('approved', 'Đã duyệt chi'),
         ('paid', 'Đã chi'),
         ('rejected', 'Từ chối')],
        string='Trạng thái', default='draft', required=True, tracking=True,
        copy=False)
    payment_id = fields.Many2one('account.payment', string='Phiếu chi',
                                 readonly=True, copy=False)
    currency_id = fields.Many2one(
        'res.currency', string='Đồng tiền', required=True,
        default=lambda self: self.env.company.currency_id)
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company, index=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('Mới')) == _('Mới'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'rp.payment.request') or _('ĐN mới')
        return super().create(vals_list)

    @api.onchange('purchase_order_id')
    def _onchange_po(self):
        if self.purchase_order_id:
            self.partner_id = self.purchase_order_id.partner_id
            self.project_id = self.purchase_order_id.rp_project_id
            self.currency_id = self.purchase_order_id.currency_id

    @api.onchange('receipt_id')
    def _onchange_receipt(self):
        # Lấy theo GIÁ TRỊ NGHIỆM THU, không theo giá trị đơn mua.
        if self.receipt_id:
            self.amount = self.receipt_id.amount_accepted
            if not self.reason:
                self.reason = _(
                    'Thanh toán theo biên bản nghiệm thu %s.',
                    self.receipt_id.name)

    def action_trinh_duyet(self):
        for r in self:
            if r.purchase_order_id and not r.receipt_id:
                raise UserError(_(
                    'Đề nghị "%s" gắn đơn mua nhưng chưa có biên bản '
                    'nghiệm thu. Chưa nghiệm thu thì chưa có căn cứ chi.',
                    r.name))
            r.state = 'to_approve'
        return True

    def action_duyet(self):
        self.write({'state': 'approved', 'approver_id': self.env.user.id})
        return True

    def action_tu_choi(self):
        self.write({'state': 'rejected', 'approver_id': self.env.user.id})
        return True

    def action_ve_nhap(self):
        self.write({'state': 'draft', 'approver_id': False})
        return True

    def action_danh_dau_da_chi(self):
        for r in self:
            if r.state != 'approved':
                raise UserError(_(
                    'Chỉ đánh dấu đã chi cho đề nghị ĐÃ DUYỆT.'))
            r.state = 'paid'
        return True
