# -*- coding: utf-8 -*-
"""Điều chuyển giữa kho có HÀNG ĐANG ĐI (KHO-21).

Chuyển thẳng một nhịp thì có một quãng hàng **không ở đâu cả**: kho gửi
đã trừ, kho nhận chưa cộng. Với hai kho cách nhau 400 km thì quãng đó là
vài ngày, và đó đúng là lúc hàng hay mất.

Nên chuyển đi hai nhịp qua vị trí **trung chuyển**:

1. Kho gửi → Trung chuyển  (lúc xe rời kho)
2. Trung chuyển → Kho nhận (lúc người nhận XÁC NHẬN đã nhận đủ)

Giữa hai nhịp, hàng nằm ở Trung chuyển — đếm được, tra được, và thuộc
trách nhiệm của bên gửi cho tới khi bên nhận ký.

Nhận THIẾU thì phần thiếu nằm lại Trung chuyển, không tự bốc hơi. Có
người phải đi tìm, và sổ phải chỉ ra được là đang thiếu bao nhiêu.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class EamStockTransfer(models.Model):
    _name = 'eam.stock.transfer'
    _description = 'Điều chuyển giữa kho'
    _inherit = ['mail.thread']
    _order = 'date desc, id desc'

    name = fields.Char(string='Số phiếu', required=True, copy=False,
                       readonly=True, default=lambda s: _('Mới'))
    date = fields.Date(string='Ngày gửi', required=True, tracking=True,
                       default=fields.Date.context_today)
    warehouse_from_id = fields.Many2one(
        'stock.warehouse', string='Kho gửi', required=True, tracking=True)
    warehouse_to_id = fields.Many2one(
        'stock.warehouse', string='Kho nhận', required=True, tracking=True)
    line_ids = fields.One2many(
        'eam.stock.transfer.line', 'transfer_id', string='Vật tư')
    date_received = fields.Date(string='Ngày nhận', readonly=True,
                                tracking=True)
    receiver_id = fields.Many2one('res.users', string='Người nhận',
                                  readonly=True, tracking=True)
    state = fields.Selection(
        [('draft', 'Nháp'),
         ('in_transit', 'Đang đi'),
         ('done', 'Đã nhận'),
         ('cancelled', 'Đã huỷ')],
        string='Trạng thái', default='draft', required=True, tracking=True,
        copy=False)
    con_thieu = fields.Boolean(string='Còn hàng đang đi',
                               compute='_compute_con_thieu', store=True)
    note = fields.Text(string='Ghi chú')
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda s: s.env.company)

    @api.depends('line_ids.qty_sent', 'line_ids.qty_received', 'state')
    def _compute_con_thieu(self):
        for r in self:
            r.con_thieu = r.state == 'done' and any(
                l.qty_received < l.qty_sent for l in r.line_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for v in vals_list:
            if v.get('name', _('Mới')) == _('Mới'):
                v['name'] = self.env['ir.sequence'].next_by_code(
                    'eam.stock.transfer') or _('Mới')
        return super().create(vals_list)

    @api.constrains('warehouse_from_id', 'warehouse_to_id')
    def _check_khac_kho(self):
        for r in self:
            if r.warehouse_from_id == r.warehouse_to_id:
                raise UserError(_('Kho gửi và kho nhận phải khác nhau.'))

    def _vi_tri_trung_chuyen(self):
        """Vị trí trung chuyển dùng chung của công ty."""
        L = self.env['stock.location']
        # Odoo dựng sẵn vị trí chuyển tiếp liên kho, nhưng tên và chủ sở
        # hữu khác nhau tuỳ cấu hình — ưu tiên đúng công ty, không có thì
        # lấy loại dùng chung, cuối cùng mới tự tạo.
        x = L.search([('usage', '=', 'transit'),
                      ('company_id', '=', self.company_id.id)], limit=1)
        if not x:
            x = L.search([('usage', '=', 'transit'),
                          ('company_id', '=', False)], limit=1)
        if not x:
            x = L.create({'name': 'Hàng đang đi giữa kho',
                          'usage': 'transit',
                          'company_id': self.company_id.id})
        return x

    def _tao_phieu(self, src, dst, cap_so):
        Move = self.env['stock.move']
        ML = self.env['stock.move.line']
        for l in self.line_ids:
            sl = cap_so(l)
            if sl <= 0:
                continue
            mv = Move.create({
                'product_id': l.product_id.id,
                'product_uom': l.uom_id.id,
                'product_uom_qty': sl,
                'location_id': src.id, 'location_dest_id': dst.id,
                'company_id': self.company_id.id,
            })
            mv._action_confirm()
            mv.move_line_ids.unlink()
            ML.create({
                'move_id': mv.id, 'product_id': l.product_id.id,
                'product_uom_id': l.uom_id.id, 'quantity': sl,
                'lot_id': l.lot_id.id if l.lot_id else False,
                'location_id': src.id, 'location_dest_id': dst.id,
                'company_id': self.company_id.id,
            })
            mv.picked = True
            mv._action_done()

    def action_gui(self):
        for r in self:
            if r.state != 'draft':
                raise UserError(_('Phiếu "%s" đã gửi rồi.', r.name))
            if not r.line_ids:
                raise UserError(_('Phiếu "%s" chưa có dòng nào.', r.name))
            src = r.warehouse_from_id.lot_stock_id
            for l in r.line_ids:
                con = l.product_id.with_context(
                    location=src.id).free_qty
                if con < l.qty_sent:
                    raise UserError(_(
                        'Kho "%(kho)s" chỉ còn %(con)g khả dụng "%(sp)s", '
                        'cần gửi %(can)g.', kho=src.complete_name, con=con,
                        sp=l.product_id.display_name, can=l.qty_sent))
            r._tao_phieu(src, r._vi_tri_trung_chuyen(),
                         lambda l: l.qty_sent)
            r.state = 'in_transit'
            r.message_post(body=_(
                'Đã gửi %(n)d dòng từ "%(a)s". Hàng đang ở vị trí trung '
                'chuyển cho tới khi "%(b)s" xác nhận nhận.',
                n=len(r.line_ids), a=r.warehouse_from_id.name,
                b=r.warehouse_to_id.name))
        return True

    def action_nhan(self):
        """Bên nhận ký. Phần thiếu NẰM LẠI trung chuyển, không bốc hơi."""
        for r in self:
            if r.state != 'in_transit':
                raise UserError(_(
                    'Phiếu "%s" chưa ở trạng thái đang đi.', r.name))
            for l in r.line_ids:
                if l.qty_received > l.qty_sent:
                    raise UserError(_(
                        'Dòng "%(sp)s": nhận %(n)g nhiều hơn gửi %(g)g.',
                        sp=l.product_id.display_name, n=l.qty_received,
                        g=l.qty_sent))
            r._tao_phieu(r._vi_tri_trung_chuyen(),
                         r.warehouse_to_id.lot_stock_id,
                         lambda l: l.qty_received)
            r.state = 'done'
            r.date_received = fields.Date.context_today(r)
            r.receiver_id = self.env.user.id
            thieu = [(l.product_id.display_name, l.qty_sent - l.qty_received)
                     for l in r.line_ids if l.qty_received < l.qty_sent]
            if thieu:
                r.message_post(body=_(
                    'Nhận THIẾU: %s. Phần thiếu vẫn nằm ở vị trí trung '
                    'chuyển — phải tìm ra, không tự xoá.',
                    ', '.join('%s (%g)' % t for t in thieu)))
        return True

    def action_huy(self):
        for r in self:
            if r.state != 'draft':
                raise UserError(_(
                    'Đã gửi rồi thì không huỷ — hàng đang trên đường. Ghi '
                    'nhận nhận thiếu rồi xử lý phần thiếu.'))
            r.state = 'cancelled'
        return True


class EamStockTransferLine(models.Model):
    _name = 'eam.stock.transfer.line'
    _description = 'Dòng điều chuyển'
    _order = 'transfer_id, id'

    transfer_id = fields.Many2one(
        'eam.stock.transfer', string='Phiếu', required=True,
        ondelete='cascade', index=True)
    product_id = fields.Many2one(
        'product.product', string='Vật tư', required=True,
        domain="[('is_storable', '=', True)]")
    lot_id = fields.Many2one(
        'stock.lot', string='Sê-ri / lô',
        domain="[('product_id', '=', product_id)]")
    uom_id = fields.Many2one('uom.uom', string='Đơn vị')
    qty_sent = fields.Float(string='SL gửi', required=True, default=1.0,
                            digits='Product Unit of Measure')
    qty_received = fields.Float(string='SL nhận',
                                digits='Product Unit of Measure')
    chenh = fields.Float(string='Chênh lệch', compute='_compute_chenh',
                         store=True, digits='Product Unit of Measure')
    company_id = fields.Many2one(related='transfer_id.company_id', store=True)

    @api.depends('qty_sent', 'qty_received')
    def _compute_chenh(self):
        for l in self:
            l.chenh = (l.qty_received or 0.0) - (l.qty_sent or 0.0)

    @api.onchange('product_id')
    def _onchange_product(self):
        for l in self:
            if l.product_id:
                l.uom_id = l.product_id.uom_id
                l.qty_received = l.qty_sent
