# -*- coding: utf-8 -*-
"""Yêu cầu vật tư (KHO-16), duyệt theo thẩm quyền (KHO-18), xuất khẩn cấp
(KHO-19).

Ba chứng từ tên gần giống nhau, ĐỪNG lẫn
-----------------------------------------
* ``eam.work.request``  — yêu cầu **công việc**: báo có việc cần làm.
* ``rp.purchase.request`` — yêu cầu **mua**: xin tiền mua thứ chưa có.
* ``eam.material.request`` (ở đây) — yêu cầu **vật tư**: xin thứ ĐÃ CÓ
  trong kho.

Không tách bạch ba cái này thì sáu tháng nữa sẽ có hai cửa vào cùng một
chỗ với hai bộ luật, và người ta sẽ đi cửa ngắn.

Vì sao cần chứng từ riêng, không xin thẳng trên lệnh công việc
---------------------------------------------------------------
Lệnh công việc là của thợ. Kho là của thủ kho. Khi hai bên tranh nhau một
con hộp số duy nhất, cần một chỗ ghi **ai xin trước, ai duyệt, duyệt lúc
nào** — lệnh công việc không có chỗ đó, và cũng không nên có.

Xuất khẩn cấp: cho đi trước, NHƯNG ghi nợ hồ sơ
------------------------------------------------
Sự cố lúc 2 giờ sáng thì không ai chờ duyệt. Chặn cứng ở đây là đẩy người
ta sang đường vòng — lấy hàng không ghi sổ, và đó là cách mất dấu nhanh
nhất.

Nên khẩn cấp được **bỏ qua duyệt**, đổi lại phải khai đủ *ai nhận, cho
thiết bị nào, vì sao*, và hệ thống **ghi nợ một hồ sơ chưa hoàn thiện**
kèm hạn. Món nợ đó hiện trong danh sách riêng cho tới khi có người đóng.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError

MUC_KHAN = [
    ('normal', 'Bình thường'),
    ('urgent', 'Gấp — máy đang chờ'),
    ('emergency', 'Khẩn cấp — sự cố, dừng máy'),
]


class EamApprovalRule(models.Model):
    _name = 'eam.approval.rule'
    _description = 'Luật duyệt yêu cầu vật tư'
    _order = 'sequence, id'

    name = fields.Char(string='Tên luật', required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    amount_from = fields.Monetary(
        string='Giá trị từ', currency_field='currency_id',
        help='Tổng giá trị yêu cầu từ mức này trở lên thì luật áp dụng.')
    part_kind = fields.Selection(
        [('spare', 'Phụ tùng thay thế'), ('consumable', 'Vật tư tiêu hao'),
         ('lubricant', 'Dầu mỡ, hoá chất'), ('tool', 'Dụng cụ')],
        string='Chỉ áp cho loại',
        help='Bỏ trống là áp cho mọi loại.')
    criticality = fields.Selection(
        [('high', 'Cao trở lên'), ('critical', 'Trọng yếu')],
        string='Chỉ áp khi mức quan trọng',
        help='Bỏ trống là không xét mức quan trọng.')
    rotable_only = fields.Boolean(
        string='Chỉ áp cho vật tư quay vòng',
        help='Hộp số, máy phát, cánh, bộ biến đổi — thứ tháo ra đem đại '
             'tu rồi lắp lại.')
    group_id = fields.Many2one(
        'res.groups', string='Nhóm được duyệt', required=True,
        help='Ai thuộc nhóm này thì duyệt được cấp này.')
    currency_id = fields.Many2one(
        'res.currency', default=lambda s: s.env.company.currency_id)
    note = fields.Char(string='Diễn giải')

    def _ap_dung_cho(self, req):
        """Luật này có áp cho yêu cầu đó không."""
        self.ensure_one()
        if self.amount_from and req.amount_total < self.amount_from:
            return False
        dong = req.line_ids
        if self.part_kind:
            dong = dong.filtered(
                lambda l: l.product_id.eam_part_kind == self.part_kind)
        if self.criticality:
            muc = (('high', 'critical') if self.criticality == 'high'
                   else ('critical',))
            dong = dong.filtered(
                lambda l: l.product_id.eam_criticality in muc)
        if self.rotable_only:
            dong = dong.filtered(lambda l: l.product_id.eam_is_rotable)
        return bool(dong)


class EamMaterialRequest(models.Model):
    _name = 'eam.material.request'
    _description = 'Yêu cầu vật tư'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(string='Số yêu cầu', required=True, copy=False,
                       readonly=True, default=lambda s: _('Mới'))
    date = fields.Date(string='Ngày yêu cầu', required=True, tracking=True,
                       default=fields.Date.context_today)
    requester_id = fields.Many2one(
        'res.users', string='Người yêu cầu', required=True, tracking=True,
        default=lambda s: s.env.user)
    warehouse_id = fields.Many2one(
        'stock.warehouse', string='Xin ở kho', required=True, tracking=True)

    # --- nguồn phát sinh: ba đường, đúng như yêu cầu nghiệp vụ nêu ---
    source = fields.Selection(
        [('wo', 'Lệnh công việc'),
         ('outage', 'Sự cố / dừng máy'),
         ('pm', 'Kế hoạch bảo trì')],
        string='Phát sinh từ', required=True, default='wo', tracking=True)
    work_order_id = fields.Many2one(
        'eam.work.order', string='Lệnh công việc', tracking=True)
    outage_id = fields.Many2one('eam.outage', string='Lần dừng máy')
    pm_schedule_id = fields.Many2one(
        'eam.pm.schedule', string='Lịch bảo trì')
    location_id = fields.Many2one(
        'eam.location', string='Cho vị trí / thiết bị', tracking=True)

    urgency = fields.Selection(
        MUC_KHAN, string='Mức khẩn', required=True, default='normal',
        tracking=True)
    reason = fields.Text(string='Lý do', tracking=True)

    line_ids = fields.One2many(
        'eam.material.request.line', 'request_id', string='Vật tư xin')
    amount_total = fields.Monetary(
        string='Tổng giá trị', compute='_compute_amount', store=True,
        currency_field='currency_id')
    currency_id = fields.Many2one(
        'res.currency', default=lambda s: s.env.company.currency_id)

    approval_ids = fields.One2many(
        'eam.material.request.approval', 'request_id', string='Cấp duyệt')
    can_duyet = fields.Boolean(
        string='Bạn duyệt được', compute='_compute_can_duyet')

    state = fields.Selection(
        [('draft', 'Nháp'),
         ('to_approve', 'Chờ duyệt'),
         ('approved', 'Đã duyệt'),
         ('issued', 'Đã cấp phát'),
         ('rejected', 'Từ chối'),
         ('cancelled', 'Đã huỷ')],
        string='Trạng thái', default='draft', required=True, tracking=True,
        copy=False)

    # --- xuất khẩn cấp: nợ hồ sơ ---
    is_emergency = fields.Boolean(
        string='Xuất khẩn cấp', compute='_compute_emergency', store=True)
    receiver_name = fields.Char(string='Người nhận hàng', tracking=True)
    ho_so_du = fields.Boolean(
        string='Hồ sơ đã hoàn thiện', tracking=True, copy=False,
        help='Xuất khẩn cấp cho đi trước, hồ sơ theo sau. Chừng nào ô này '
             'chưa tích thì yêu cầu còn nằm trong danh sách nợ hồ sơ.')
    han_hoan_thien = fields.Date(
        string='Hạn hoàn thiện hồ sơ', copy=False)
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda s: s.env.company)

    @api.depends('line_ids.amount')
    def _compute_amount(self):
        for r in self:
            r.amount_total = sum(r.line_ids.mapped('amount'))

    @api.depends('urgency')
    def _compute_emergency(self):
        for r in self:
            r.is_emergency = r.urgency == 'emergency'

    @api.depends('approval_ids.state', 'approval_ids.group_id')
    def _compute_can_duyet(self):
        for r in self:
            cho = r.approval_ids.filtered(lambda a: a.state == 'pending')
            r.can_duyet = any(
                self.env.user.has_group(a.group_id.full_name or '')
                or a.group_id in self.env.user.all_group_ids
                for a in cho)

    @api.model_create_multi
    def create(self, vals_list):
        for v in vals_list:
            if v.get('name', _('Mới')) == _('Mới'):
                v['name'] = self.env['ir.sequence'].next_by_code(
                    'eam.material.request') or _('Mới')
        return super().create(vals_list)

    # ------------------------------------------------------------------
    def _kiem_truoc_khi_trinh(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_(
                'Yêu cầu "%s" chưa có dòng vật tư nào.', self.name))
        if self.source == 'wo' and not self.work_order_id:
            raise UserError(_(
                'Phát sinh từ lệnh công việc thì phải chỉ rõ lệnh nào — '
                'nếu không thì chi phí vật tư không về được lệnh.'))
        if self.source == 'outage' and not self.outage_id:
            raise UserError(_('Chưa chỉ rõ lần dừng máy.'))

    def action_trinh_duyet(self):
        A = self.env['eam.material.request.approval']
        for r in self:
            r._kiem_truoc_khi_trinh()
            if r.is_emergency:
                raise UserError(_(
                    'Yêu cầu khẩn cấp không đi đường trình duyệt — bấm '
                    '"Cấp phát khẩn cấp".'))
            r.approval_ids.unlink()
            luat = self.env['eam.approval.rule'].search([])
            ap = [l for l in luat if l._ap_dung_cho(r)]
            if not ap:
                # Không luật nào áp thì KHÔNG phải là "ai cũng duyệt
                # được" — nghĩa là giá trị nhỏ, dưới mọi ngưỡng, duyệt
                # luôn. Để treo chờ một người duyệt không tồn tại là cách
                # chắc chắn làm tắc kho.
                r.state = 'approved'
                r.message_post(body=_(
                    'Không luật duyệt nào áp dụng (giá trị dưới mọi '
                    'ngưỡng) — duyệt tự động.'))
                continue
            # Gộp theo NHÓM: ba luật cùng trỏ về quản lý kho thì vẫn chỉ
            # là một cấp duyệt. Bắt cùng một người bấm duyệt ba lần không
            # làm chứng từ chặt hơn, chỉ làm người ta bấm cho xong.
            theo_nhom = {}
            for l in ap:
                theo_nhom.setdefault(l.group_id.id, []).append(l)
            for i, (gid, ds) in enumerate(theo_nhom.items()):
                A.create({'request_id': r.id, 'rule_id': ds[0].id,
                          'group_id': gid, 'sequence': i + 1})
            r.state = 'to_approve'
        return True

    def action_duyet(self):
        for r in self:
            cho = r.approval_ids.filtered(lambda a: a.state == 'pending')
            minh = cho.filtered(
                lambda a: a.group_id in self.env.user.all_group_ids)
            if not minh:
                raise UserError(_(
                    'Bạn không thuộc cấp duyệt nào đang chờ của yêu cầu '
                    '"%(ten)s".\n\nĐang chờ: %(ds)s', ten=r.name,
                    ds=', '.join(cho.mapped('group_id.name')) or '-'))
            minh.write({'state': 'approved',
                        'user_id': self.env.user.id,
                        'date_action': fields.Datetime.now()})
            if not r.approval_ids.filtered(lambda a: a.state == 'pending'):
                r.state = 'approved'
        return True

    def action_tu_choi(self):
        for r in self:
            cho = r.approval_ids.filtered(lambda a: a.state == 'pending')
            minh = cho.filtered(
                lambda a: a.group_id in self.env.user.all_group_ids)
            if not minh:
                raise UserError(_(
                    'Bạn không thuộc cấp duyệt nào đang chờ.'))
            minh.write({'state': 'rejected', 'user_id': self.env.user.id,
                        'date_action': fields.Datetime.now()})
            r.state = 'rejected'
        return True

    # ------------------------------------------------------------------
    def action_cap_phat_khan(self):
        """Cho hàng đi ngay, ghi nợ hồ sơ."""
        for r in self:
            if not r.is_emergency:
                raise UserError(_(
                    'Chỉ yêu cầu mức "Khẩn cấp" mới đi đường này. Yêu cầu '
                    'thường phải trình duyệt.'))
            r._kiem_truoc_khi_trinh()
            thieu = [t for t, v in (
                (_('người nhận hàng'), r.receiver_name),
                (_('vị trí / thiết bị'), r.location_id),
                (_('lý do'), r.reason)) if not v]
            if thieu:
                raise UserError(_(
                    'Xuất khẩn cấp vẫn phải khai: %s.\n\nĐây là ba thứ '
                    'duy nhất còn lại để truy ngược khi hàng đã rời kho '
                    'mà chưa ai duyệt.', ', '.join(thieu)))
            r.state = 'approved'
            r.ho_so_du = False
            r.han_hoan_thien = fields.Date.add(
                fields.Date.context_today(r), days=3)
            r.message_post(body=_(
                'Cấp phát KHẨN CẤP, bỏ qua duyệt. Người nhận: %(ng)s. '
                'Hạn hoàn thiện hồ sơ: %(h)s.',
                ng=r.receiver_name, h=r.han_hoan_thien))
        return True

    def action_dong_ho_so(self):
        for r in self:
            if not r.is_emergency:
                raise UserError(_('Chỉ áp cho yêu cầu khẩn cấp.'))
            r.ho_so_du = True
            r.message_post(body=_('Đã hoàn thiện hồ sơ xuất khẩn cấp.'))
        return True


    def action_cap_phat(self):
        """Đã duyệt thì cấp phát — đi qua ĐÚNG đường xuất kho của lệnh
        công việc, không mở đường riêng.

        Mở đường xuất thứ hai là lập tức có hai bộ luật cho cùng một
        việc: một bên kiểm sê-ri và tồn, một bên không. Và người ta sẽ
        đi cửa ngắn.
        """
        for r in self:
            if r.state != 'approved':
                raise UserError(_(
                    'Yêu cầu "%s" chưa được duyệt.', r.name))
            if r.source != 'wo' or not r.work_order_id:
                raise UserError(_(
                    'Bản này cấp phát qua lệnh công việc. Yêu cầu phát '
                    'sinh từ sự cố hoặc kế hoạch bảo trì thì mở lệnh '
                    'công việc trước rồi gắn vào.'))
            wo = r.work_order_id
            if not wo.stock_location_id:
                wo.stock_location_id = r.warehouse_id.lot_stock_id.id
            Part = self.env['eam.work.order.part']
            moi = Part
            for l in r.line_ids:
                moi |= Part.create({
                    'order_id': wo.id, 'product_id': l.product_id.id,
                    'lot_id': l.lot_id.id if l.lot_id else False,
                    'qty': l.qty, 'uom_id': l.uom_id.id,
                    'unit_cost': l.unit_cost,
                    'is_rotable': l.product_id.eam_is_rotable,
                    'note': _('Theo yêu cầu vật tư %s', r.name),
                })
            wo.action_xuat_vat_tu()
            r.state = 'issued'
            r.message_post(body=_(
                'Đã cấp phát %(n)d dòng vật tư qua lệnh %(wo)s.',
                n=len(moi), wo=wo.name))
        return True

    def action_ve_nhap(self):
        for r in self:
            if r.state == 'issued':
                raise UserError(_(
                    'Yêu cầu "%s" đã cấp phát — hàng đã rời kho, không về '
                    'nháp được. Muốn thu lại thì làm hoàn trả trên lệnh '
                    'công việc.', r.name))
            r.approval_ids.unlink()
            r.state = 'draft'
        return True

    def action_huy(self):
        for r in self:
            if r.state == 'issued':
                raise UserError(_('Đã cấp phát rồi thì không huỷ được.'))
            r.state = 'cancelled'
        return True


class EamMaterialRequestLine(models.Model):
    _name = 'eam.material.request.line'
    _description = 'Dòng yêu cầu vật tư'
    _order = 'request_id, id'

    request_id = fields.Many2one(
        'eam.material.request', string='Yêu cầu', required=True,
        ondelete='cascade', index=True)
    product_id = fields.Many2one(
        'product.product', string='Vật tư', required=True,
        domain="[('is_storable', '=', True)]")
    lot_id = fields.Many2one(
        'stock.lot', string='Sê-ri / lô',
        domain="[('product_id', '=', product_id)]")
    qty = fields.Float(string='Số lượng', required=True, default=1.0,
                       digits='Product Unit of Measure')
    uom_id = fields.Many2one('uom.uom', string='Đơn vị')
    unit_cost = fields.Monetary(string='Đơn giá',
                                currency_field='currency_id')
    amount = fields.Monetary(string='Thành tiền', compute='_compute_amount',
                             store=True, currency_field='currency_id')
    ton_kha_dung = fields.Float(
        string='Khả dụng', compute='_compute_ton',
        digits='Product Unit of Measure')
    currency_id = fields.Many2one(
        related='request_id.currency_id', store=True)
    company_id = fields.Many2one(related='request_id.company_id', store=True)

    @api.depends('qty', 'unit_cost')
    def _compute_amount(self):
        for l in self:
            l.amount = (l.qty or 0.0) * (l.unit_cost or 0.0)

    @api.depends('product_id', 'request_id.warehouse_id')
    def _compute_ton(self):
        for l in self:
            kho = l.request_id.warehouse_id
            l.ton_kha_dung = (
                l.product_id.with_context(
                    location=kho.lot_stock_id.id).free_qty
                if l.product_id and kho else 0.0)

    @api.onchange('product_id')
    def _onchange_product(self):
        for l in self:
            if l.product_id:
                l.uom_id = l.product_id.uom_id
                l.unit_cost = l.product_id.standard_price


class EamMaterialRequestApproval(models.Model):
    _name = 'eam.material.request.approval'
    _description = 'Cấp duyệt yêu cầu vật tư'
    _order = 'request_id, sequence, id'

    request_id = fields.Many2one(
        'eam.material.request', string='Yêu cầu', required=True,
        ondelete='cascade', index=True)
    sequence = fields.Integer(string='Cấp', default=1)
    rule_id = fields.Many2one('eam.approval.rule', string='Theo luật')
    group_id = fields.Many2one('res.groups', string='Nhóm duyệt',
                               required=True)
    user_id = fields.Many2one('res.users', string='Người đã xử lý',
                              readonly=True)
    date_action = fields.Datetime(string='Lúc', readonly=True)
    state = fields.Selection(
        [('pending', 'Chờ'), ('approved', 'Đã duyệt'),
         ('rejected', 'Từ chối')],
        string='Trạng thái', default='pending', required=True)
