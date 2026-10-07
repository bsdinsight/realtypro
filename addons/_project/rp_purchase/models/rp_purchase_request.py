# -*- coding: utf-8 -*-
"""Yêu cầu mua sắm (PR) — đầu chuỗi mua sắm của chủ đầu tư.

Chuỗi đầy đủ: YÊU CẦU → ĐƠN MUA → NHẬN HÀNG & NGHIỆM THU → ĐỀ NGHỊ
THANH TOÁN → HOÁ ĐƠN → THANH TOÁN.

Tách yêu cầu khỏi đơn mua vì hai thứ khác chủ thể: yêu cầu do bộ phận
CẦN DÙNG lập (ban điều hành công trường, phòng kỹ thuật, O&M), đơn mua
do bộ phận MUA lập sau khi đã duyệt và đã chọn được nhà cung cấp. Gộp
làm một thì không bao giờ trả lời được "ai là người xin khoản chi này",
mà đó chính là câu kiểm toán hỏi đầu tiên.

Một yêu cầu có thể ra NHIỀU đơn mua (chia theo nhà cung cấp), nên liên
kết là một-nhiều chứ không phải một-một.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class RpPurchaseRequest(models.Model):
    _name = 'rp.purchase.request'
    _description = 'Yêu cầu mua sắm'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_request desc, id desc'

    name = fields.Char(string='Số yêu cầu', required=True, copy=False,
                       default=lambda self: _('Mới'), tracking=True)
    project_id = fields.Many2one(
        're.project', string='Dự án', index=True, ondelete='restrict',
        tracking=True,
        help='Để trống nếu là mua sắm chung của công ty, không thuộc dự '
             'án nào.')
    requester_id = fields.Many2one(
        'res.users', string='Người đề nghị', required=True, tracking=True,
        default=lambda self: self.env.user)
    department = fields.Char(string='Bộ phận đề nghị')
    date_request = fields.Date(
        string='Ngày đề nghị', required=True, tracking=True,
        default=fields.Date.context_today)
    date_required = fields.Date(
        string='Cần hàng trước ngày', tracking=True,
        help='Mốc này quyết định mua kịp hay không — thiếu nó thì bộ '
             'phận mua không biết việc nào gấp.')
    reason = fields.Text(string='Lý do / căn cứ', required=True)
    state = fields.Selection(
        [('draft', 'Nháp'),
         ('to_approve', 'Chờ duyệt'),
         ('approved', 'Đã duyệt'),
         ('rejected', 'Từ chối'),
         ('done', 'Đã ra đơn mua'),
         ('cancelled', 'Huỷ')],
        string='Trạng thái', default='draft', required=True, tracking=True,
        copy=False)
    approver_id = fields.Many2one('res.users', string='Người duyệt',
                                  readonly=True, tracking=True)
    date_approved = fields.Date(string='Ngày duyệt', readonly=True)
    line_ids = fields.One2many(
        'rp.purchase.request.line', 'request_id', string='Nội dung')
    amount_estimated = fields.Monetary(
        string='Giá trị ước tính', compute='_compute_tong', store=True,
        currency_field='currency_id')
    purchase_order_ids = fields.One2many(
        'purchase.order', 'rp_request_id', string='Đơn mua đã ra')
    purchase_order_count = fields.Integer(compute='_compute_tong')
    currency_id = fields.Many2one(
        'res.currency', string='Đồng tiền',
        default=lambda self: self.env.company.currency_id)
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company, index=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('Mới')) == _('Mới'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'rp.purchase.request') or _('YC mới')
        return super().create(vals_list)

    @api.depends('line_ids.amount_estimated', 'purchase_order_ids')
    def _compute_tong(self):
        for r in self:
            r.amount_estimated = sum(r.line_ids.mapped('amount_estimated'))
            r.purchase_order_count = len(r.purchase_order_ids)

    def action_trinh_duyet(self):
        for r in self:
            if not r.line_ids:
                raise UserError(_(
                    'Yêu cầu "%s" chưa có nội dung nào.', r.name))
            r.state = 'to_approve'
        return True

    def action_duyet(self):
        for r in self:
            r.write({'state': 'approved',
                     'approver_id': self.env.user.id,
                     'date_approved': fields.Date.context_today(self)})
        return True

    def action_tu_choi(self):
        self.write({'state': 'rejected', 'approver_id': self.env.user.id})
        return True

    def action_ve_nhap(self):
        self.write({'state': 'draft', 'approver_id': False,
                    'date_approved': False})
        return True

    def action_tao_don_mua(self):
        """Ra đơn mua từ yêu cầu đã duyệt — gom theo NHÀ CUNG CẤP.

        Một yêu cầu có thể cần nhiều nhà cung cấp; ép một đơn duy nhất
        thì người mua phải tách tay, và họ sẽ gán bừa một nhà cung cấp
        cho cả yêu cầu.
        """
        self.ensure_one()
        if self.state != 'approved':
            raise UserError(_(
                'Chỉ ra đơn mua từ yêu cầu ĐÃ DUYỆT. Hiện: %s.',
                dict(self._fields['state'].selection).get(self.state)))
        chua_ncc = self.line_ids.filtered(lambda l: not l.partner_id)
        if chua_ncc:
            raise UserError(_(
                'Còn %d dòng chưa chọn nhà cung cấp — chưa biết đặt hàng '
                'của ai.', len(chua_ncc)))
        PO = self.env['purchase.order']
        tao = PO
        for ncc in self.line_ids.mapped('partner_id'):
            dong = self.line_ids.filtered(lambda l: l.partner_id == ncc)
            tao |= PO.create({
                'partner_id': ncc.id,
                'rp_project_id': self.project_id.id,
                'rp_request_id': self.id,
                'currency_id': self.currency_id.id,
                'order_line': [(0, 0, {
                    'product_id': l.product_id.id,
                    'name': l.name,
                    'product_qty': l.quantity,
                    'price_unit': l.price_estimated,
                    'rp_cost_category_id': l.cost_category_id.id,
                    'date_planned': fields.Datetime.now(),
                }) for l in dong],
            })
        self.state = 'done'
        return {
            'type': 'ir.actions.act_window', 'name': _('Đơn mua đã ra'),
            'res_model': 'purchase.order', 'view_mode': 'list,form',
            'domain': [('id', 'in', tao.ids)],
        }

    def action_mo_don_mua(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': _('Đơn mua'),
            'res_model': 'purchase.order', 'view_mode': 'list,form',
            'domain': [('rp_request_id', '=', self.id)],
        }


class RpPurchaseRequestLine(models.Model):
    _name = 'rp.purchase.request.line'
    _description = 'Dòng yêu cầu mua sắm'
    _order = 'request_id, sequence, id'

    request_id = fields.Many2one(
        'rp.purchase.request', string='Yêu cầu', required=True,
        index=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    name = fields.Char(string='Nội dung', required=True)
    product_id = fields.Many2one(
        'product.product', string='Sản phẩm / dịch vụ',
        domain="[('purchase_ok', '=', True)]")
    quantity = fields.Float(string='Số lượng', default=1.0, required=True)
    price_estimated = fields.Monetary(
        string='Đơn giá ước tính', currency_field='currency_id')
    amount_estimated = fields.Monetary(
        string='Thành tiền', compute='_compute_thanh_tien', store=True,
        currency_field='currency_id')
    cost_category_id = fields.Many2one(
        'rp.cost.category', string='Nhóm chi phí',
        domain="[('project_id', '=', project_id)]")
    partner_id = fields.Many2one(
        'res.partner', string='Nhà cung cấp đề xuất',
        domain="[('supplier_rank', '>', 0)]")
    project_id = fields.Many2one(
        're.project', related='request_id.project_id', readonly=True)
    currency_id = fields.Many2one(
        'res.currency', related='request_id.currency_id', readonly=True)

    @api.depends('quantity', 'price_estimated')
    def _compute_thanh_tien(self):
        for l in self:
            l.amount_estimated = (l.quantity or 0.0) * (l.price_estimated or 0.0)
