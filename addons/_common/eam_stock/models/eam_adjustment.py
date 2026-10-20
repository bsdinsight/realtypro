# -*- coding: utf-8 -*-
"""Điều chỉnh tồn có duyệt (KHO-32) và thanh lý vật tư (KHO-38).

Vì sao không dùng thẳng điều chỉnh tồn của Odoo
-------------------------------------------------
Odoo cho sửa số tồn **ngay lập tức**, một người làm là xong, lý do để
trống cũng được. Với vật tư vài tỷ một con thì đó là lỗ hổng: số liệu
sai do đếm nhầm và số liệu sai do mất hàng trông giống hệt nhau trên
màn hình.

Phiếu này thêm ba thứ Odoo không có: **bắt buộc lý do**, **phải duyệt
khi giá trị lớn**, và **lưu cả số trước lẫn số sau** để sau này còn đối
chiếu được.

Bẫy chịu lực: tồn đổi giữa lúc đếm và lúc duyệt
-------------------------------------------------
Đếm hôm nay, duyệt ngày mai. Trong khoảng đó kho vẫn xuất nhập bình
thường. Áp thẳng con số đã đếm vào là **xoá mất những phát sinh hợp lệ
của người khác** — và không ai biết, vì tồn mới trông vẫn hợp lý.

Nên lúc duyệt phải đọc lại tồn hệ thống và **so với số đã ghi lúc đếm**.
Khác nhau thì dừng, bắt đếm lại. Thà phiền một lần còn hơn âm thầm ghi
đè việc của người khác.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError

LY_DO_DC = [
    ('count', 'Kiểm kê thực tế lệch sổ'),
    ('damage', 'Hư hỏng trong lưu kho'),
    ('expired', 'Hết hạn sử dụng'),
    ('lost', 'Thất lạc / mất'),
    ('found', 'Tìm thấy hàng chưa ghi sổ'),
    ('unit', 'Sai đơn vị tính khi nhập'),
    ('other', 'Khác'),
]

LY_DO_TL = [
    ('damage', 'Hư hỏng không sửa được'),
    ('expired', 'Hết hạn sử dụng'),
    ('obsolete', 'Không còn dùng cho thiết bị nào'),
    ('fail_test', 'Không đạt sau kiểm tra / đại tu'),
    ('other', 'Khác'),
]


class EamStockAdjustment(models.Model):
    _name = 'eam.stock.adjustment'
    _description = 'Phiếu điều chỉnh tồn'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(string='Số phiếu', required=True, copy=False,
                       readonly=True, default=lambda s: _('Mới'))
    date = fields.Date(string='Ngày đếm', required=True, tracking=True,
                       default=fields.Date.context_today)
    warehouse_id = fields.Many2one(
        'stock.warehouse', string='Kho', required=True, tracking=True)
    counter_id = fields.Many2one(
        'res.users', string='Người đếm', required=True, tracking=True,
        default=lambda s: s.env.user)
    approver_id = fields.Many2one('res.users', string='Người duyệt',
                                  readonly=True, tracking=True)
    date_approved = fields.Datetime(string='Duyệt lúc', readonly=True)
    reason = fields.Selection(LY_DO_DC, string='Lý do chung',
                              required=True, tracking=True)
    note = fields.Text(string='Diễn giải')
    line_ids = fields.One2many(
        'eam.stock.adjustment.line', 'adjustment_id', string='Dòng điều chỉnh')
    amount_impact = fields.Monetary(
        string='Ảnh hưởng giá trị', compute='_compute_impact', store=True,
        currency_field='currency_id',
        help='Dương là tăng tài sản, âm là giảm. Đây là con số quyết định '
             'phiếu có phải qua duyệt hay không.')
    currency_id = fields.Many2one(
        'res.currency', default=lambda s: s.env.company.currency_id)
    can_duyet = fields.Boolean(string='Cần duyệt', compute='_compute_impact',
                               store=True)
    state = fields.Selection(
        [('draft', 'Nháp'), ('to_approve', 'Chờ duyệt'),
         ('done', 'Đã áp dụng'), ('rejected', 'Từ chối'),
         ('cancelled', 'Đã huỷ')],
        string='Trạng thái', default='draft', required=True, tracking=True,
        copy=False)
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda s: s.env.company)

    NGUONG = 50000000.0   # 50 triệu: trên mức này bắt buộc có người duyệt

    @api.depends('line_ids.amount_impact')
    def _compute_impact(self):
        for r in self:
            r.amount_impact = sum(r.line_ids.mapped('amount_impact'))
            r.can_duyet = abs(r.amount_impact) >= r.NGUONG

    @api.model_create_multi
    def create(self, vals_list):
        for v in vals_list:
            if v.get('name', _('Mới')) == _('Mới'):
                v['name'] = self.env['ir.sequence'].next_by_code(
                    'eam.stock.adjustment') or _('Mới')
        return super().create(vals_list)

    def _kiem_dong(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_('Phiếu "%s" chưa có dòng nào.', self.name))
        thieu = self.line_ids.filtered(
            lambda l: abs(l.qty_diff) > 1e-6 and not l.reason)
        if thieu:
            raise UserError(_(
                'Các dòng có chênh lệch phải khai lý do: %s.\n\nSố lệch '
                'do đếm nhầm và số lệch do mất hàng trông giống hệt nhau '
                'nếu không ai ghi lại vì sao.',
                ', '.join(thieu.mapped('product_id.display_name'))[:200]))

    def action_trinh(self):
        for r in self:
            r._kiem_dong()
            if r.can_duyet:
                r.state = 'to_approve'
            else:
                r._ap_dung()
                r.message_post(body=_(
                    'Giá trị ảnh hưởng dưới ngưỡng duyệt — áp dụng ngay.'))
        return True

    def action_duyet(self):
        for r in self:
            if r.state != 'to_approve':
                raise UserError(_('Phiếu "%s" không ở trạng thái chờ duyệt.',
                                  r.name))
            if r.counter_id == self.env.user:
                raise UserError(_(
                    'Người đếm và người duyệt phải là hai người khác '
                    'nhau. Tự đếm tự duyệt thì bước duyệt không còn ý '
                    'nghĩa gì.'))
            r._ap_dung()
            r.write({'approver_id': self.env.user.id,
                     'date_approved': fields.Datetime.now()})
        return True

    def action_tu_choi(self):
        for r in self:
            r.write({'state': 'rejected', 'approver_id': self.env.user.id,
                     'date_approved': fields.Datetime.now()})
        return True

    def _ap_dung(self):
        """Áp số đã đếm vào tồn — SAU KHI đối chiếu lại tồn hệ thống."""
        Q = self.env['stock.quant'].with_context(inventory_mode=True)
        for r in self:
            lech = []
            for l in r.line_ids:
                hien = l._ton_he_thong()
                if abs(hien - l.qty_system) > 1e-6:
                    lech.append('%s @ %s: lúc đếm %g, bây giờ %g' % (
                        l.product_id.display_name, l.location_id.name,
                        l.qty_system, hien))
            if lech:
                raise UserError(_(
                    'Tồn hệ thống đã ĐỔI kể từ lúc đếm:\n\n%s\n\nÁp số cũ '
                    'vào là xoá mất những phát sinh hợp lệ trong khoảng '
                    'đó. Đếm lại rồi lập phiếu mới.', '\n'.join(lech[:6])))
            for l in r.line_ids:
                if abs(l.qty_diff) <= 1e-6:
                    continue
                q = Q.search([('product_id', '=', l.product_id.id),
                              ('location_id', '=', l.location_id.id),
                              ('lot_id', '=', l.lot_id.id or False)],
                             limit=1)
                if not q:
                    q = Q.create({'product_id': l.product_id.id,
                                  'location_id': l.location_id.id,
                                  'lot_id': l.lot_id.id or False,
                                  'inventory_quantity': l.qty_counted})
                else:
                    q.inventory_quantity = l.qty_counted
                q.inventory_quantity_set = True
                q.action_apply_inventory()
            r.state = 'done'
        return True

    def action_huy(self):
        for r in self:
            if r.state == 'done':
                raise UserError(_(
                    'Phiếu "%s" đã áp vào tồn. Muốn sửa thì lập phiếu '
                    'điều chỉnh ngược, không xoá vết cũ.', r.name))
            r.state = 'cancelled'
        return True


class EamStockAdjustmentLine(models.Model):
    _name = 'eam.stock.adjustment.line'
    _description = 'Dòng điều chỉnh tồn'
    _order = 'adjustment_id, id'

    adjustment_id = fields.Many2one(
        'eam.stock.adjustment', string='Phiếu', required=True,
        ondelete='cascade', index=True)
    product_id = fields.Many2one(
        'product.product', string='Vật tư', required=True,
        domain="[('is_storable', '=', True)]")
    lot_id = fields.Many2one(
        'stock.lot', string='Lô / sê-ri',
        domain="[('product_id', '=', product_id)]")
    location_id = fields.Many2one(
        'stock.location', string='Vị trí', required=True,
        domain="[('usage', '=', 'internal')]")
    qty_system = fields.Float(
        string='Sổ ghi (lúc đếm)', digits='Product Unit of Measure',
        help='Chụp lại lúc lập phiếu. Lúc duyệt sẽ đối chiếu với tồn hiện '
             'tại — khác nhau nghĩa là kho đã phát sinh tiếp.')
    qty_counted = fields.Float(
        string='Đếm thực tế', required=True,
        digits='Product Unit of Measure')
    qty_diff = fields.Float(
        string='Chênh lệch', compute='_compute_diff', store=True,
        digits='Product Unit of Measure')
    amount_impact = fields.Monetary(
        string='Ảnh hưởng giá trị', compute='_compute_diff', store=True,
        currency_field='currency_id')
    reason = fields.Selection(LY_DO_DC, string='Lý do')
    note = fields.Char(string='Ghi chú')
    currency_id = fields.Many2one(
        related='adjustment_id.currency_id', store=True)
    company_id = fields.Many2one(
        related='adjustment_id.company_id', store=True)

    @api.depends('qty_system', 'qty_counted', 'product_id')
    def _compute_diff(self):
        for l in self:
            l.qty_diff = (l.qty_counted or 0.0) - (l.qty_system or 0.0)
            l.amount_impact = l.qty_diff * (
                l.product_id.standard_price or 0.0)

    def _ton_he_thong(self):
        self.ensure_one()
        Q = self.env['stock.quant']
        dom = [('product_id', '=', self.product_id.id),
               ('location_id', '=', self.location_id.id)]
        if self.lot_id:
            dom.append(('lot_id', '=', self.lot_id.id))
        return sum(Q.search(dom).mapped('quantity'))

    @api.onchange('product_id', 'location_id', 'lot_id')
    def _onchange_chup_ton(self):
        for l in self:
            if l.product_id and l.location_id:
                l.qty_system = l._ton_he_thong()


class EamDisposal(models.Model):
    _name = 'eam.disposal'
    _description = 'Phiếu đề nghị thanh lý'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(string='Số phiếu', required=True, copy=False,
                       readonly=True, default=lambda s: _('Mới'))
    date = fields.Date(string='Ngày đề nghị', required=True, tracking=True,
                       default=fields.Date.context_today)
    requester_id = fields.Many2one(
        'res.users', string='Người đề nghị', required=True, tracking=True,
        default=lambda s: s.env.user)
    approver_id = fields.Many2one('res.users', string='Người duyệt',
                                  readonly=True, tracking=True)
    reason = fields.Selection(LY_DO_TL, string='Lý do', required=True,
                              tracking=True)
    note = fields.Text(string='Diễn giải')
    line_ids = fields.One2many(
        'eam.disposal.line', 'disposal_id', string='Vật tư thanh lý')
    amount_total = fields.Monetary(
        string='Giá trị thanh lý', compute='_compute_amount', store=True,
        currency_field='currency_id')
    currency_id = fields.Many2one(
        'res.currency', default=lambda s: s.env.company.currency_id)
    attachment_ids = fields.Many2many(
        'ir.attachment', 'eam_disposal_att_rel', 'disposal_id', 'att_id',
        string='Bằng chứng',
        help='Ảnh hiện trạng, biên bản giám định, kết quả kiểm tra. Thanh '
             'lý không bằng chứng thì không khác gì mất hàng.')
    state = fields.Selection(
        [('draft', 'Nháp'), ('to_approve', 'Chờ duyệt'),
         ('done', 'Đã thanh lý'), ('rejected', 'Từ chối'),
         ('cancelled', 'Đã huỷ')],
        string='Trạng thái', default='draft', required=True, tracking=True,
        copy=False)
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda s: s.env.company)

    @api.depends('line_ids.amount')
    def _compute_amount(self):
        for r in self:
            r.amount_total = sum(r.line_ids.mapped('amount'))

    @api.model_create_multi
    def create(self, vals_list):
        for v in vals_list:
            if v.get('name', _('Mới')) == _('Mới'):
                v['name'] = self.env['ir.sequence'].next_by_code(
                    'eam.disposal') or _('Mới')
        return super().create(vals_list)

    def action_trinh(self):
        for r in self:
            if not r.line_ids:
                raise UserError(_('Phiếu "%s" chưa có dòng nào.', r.name))
            if not r.attachment_ids:
                raise UserError(_(
                    'Phiếu "%s" chưa có bằng chứng nào. Thanh lý không '
                    'bằng chứng thì trên sổ không khác gì mất hàng — và '
                    'người duyệt cũng không có gì để xem mà quyết.',
                    r.name))
            r.state = 'to_approve'
        return True

    def action_duyet(self):
        """Duyệt là hàng RỜI SỔ thật — tạo phiếu loại bỏ của Odoo."""
        Scrap = self.env['stock.scrap']
        for r in self:
            if r.state != 'to_approve':
                raise UserError(_('Phiếu "%s" chưa trình duyệt.', r.name))
            if r.requester_id == self.env.user:
                raise UserError(_(
                    'Người đề nghị và người duyệt phải khác nhau.'))
            for l in r.line_ids:
                s = Scrap.create({
                    'product_id': l.product_id.id,
                    'scrap_qty': l.qty,
                    'product_uom_id': l.uom_id.id,
                    'lot_id': l.lot_id.id or False,
                    'location_id': l.location_id.id,
                    'company_id': r.company_id.id,
                })
                s.action_validate()
                l.scrap_id = s.id
            r.write({'state': 'done', 'approver_id': self.env.user.id})
        return True

    def action_tu_choi(self):
        self.write({'state': 'rejected'})
        return True


class EamDisposalLine(models.Model):
    _name = 'eam.disposal.line'
    _description = 'Dòng thanh lý'
    _order = 'disposal_id, id'

    disposal_id = fields.Many2one(
        'eam.disposal', string='Phiếu', required=True, ondelete='cascade',
        index=True)
    product_id = fields.Many2one(
        'product.product', string='Vật tư', required=True,
        domain="[('is_storable', '=', True)]")
    lot_id = fields.Many2one(
        'stock.lot', string='Lô / sê-ri',
        domain="[('product_id', '=', product_id)]")
    location_id = fields.Many2one(
        'stock.location', string='Đang ở', required=True,
        domain="[('usage', '=', 'internal')]")
    qty = fields.Float(string='Số lượng', required=True, default=1.0,
                       digits='Product Unit of Measure')
    uom_id = fields.Many2one('uom.uom', string='Đơn vị')
    amount = fields.Monetary(string='Giá trị', compute='_compute_amount',
                             store=True, currency_field='currency_id')
    scrap_id = fields.Many2one('stock.scrap', string='Phiếu loại bỏ',
                               readonly=True)
    note = fields.Char(string='Ghi chú')
    currency_id = fields.Many2one(related='disposal_id.currency_id',
                                  store=True)
    company_id = fields.Many2one(related='disposal_id.company_id',
                                 store=True)

    @api.depends('qty', 'product_id')
    def _compute_amount(self):
        for l in self:
            l.amount = (l.qty or 0.0) * (l.product_id.standard_price or 0.0)

    @api.onchange('product_id')
    def _onchange_product(self):
        for l in self:
            if l.product_id:
                l.uom_id = l.product_id.uom_id
