# -*- coding: utf-8 -*-
"""Kiểm tra đầu vào (KHO-14) và sai lệch nhận hàng (KHO-15).

Hàng về KHÔNG vào thẳng kho khả dụng. Nó vào *Chờ kiểm tra* — một vị trí
mang cờ "không dùng được" — rồi chỉ rời khỏi đó khi có người ký nhận là
đạt. Đây là luật 1 trong yêu cầu nghiệp vụ: *hàng chờ kiểm tra không tính
vào tồn khả dụng*.

Vì sao không dùng thẳng phiếu nhập của Odoo
--------------------------------------------
Phiếu nhập ghi **đã nhận bao nhiêu**. Nó không có chỗ ghi **nhận rồi thấy
sao**: đủ hay thiếu, đúng mã hay sai mã, còn nguyên hay móp vỡ, có chứng
chỉ đi kèm hay không. Nhét mấy thứ đó vào ghi chú của phiếu nhập thì
không thống kê được, và sáu tháng sau không ai trả lời nổi câu "nhà cung
cấp này giao sai mấy lần".

Phiếu này cũng KHÔNG thay phiếu nhập — nó đọc phiếu nhập rồi quyết hàng
đi đâu tiếp.

Sai lệch thì hàng đi đâu
-------------------------
* **Đạt** → về đúng ô chứa đã định, thành tồn khả dụng.
* **Không đạt** → vào *Cách ly*, nằm im chờ xử lý với bên giao. KHÔNG trả
  thẳng về nhà cung cấp trong cùng một thao tác: trả hàng là việc có
  chứng từ riêng, và lắm khi còn phải chờ họ đồng ý.

Để hàng không đạt nằm chung kho khả dụng là cách chắc chắn có người lấy
nhầm — nhất là lúc gấp.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError

LY_DO_SAI_LECH = [
    ('thieu', 'Giao thiếu'),
    ('thua', 'Giao thừa'),
    ('sai_ma', 'Sai mã / sai chủng loại'),
    ('hu_hong', 'Hư hỏng, móp vỡ'),
    ('thieu_hs', 'Thiếu chứng chỉ / hồ sơ'),
    ('khong_dat_ky_thuat', 'Không đạt thông số kỹ thuật'),
    ('khac', 'Khác'),
]


class EamInboundCheck(models.Model):
    _name = 'eam.inbound.check'
    _description = 'Phiếu kiểm tra đầu vào'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(string='Số phiếu', required=True, copy=False,
                       readonly=True, default=lambda s: _('Mới'))
    picking_id = fields.Many2one(
        'stock.picking', string='Phiếu nhập kho', ondelete='restrict',
        domain="[('picking_type_code', '=', 'incoming')]", tracking=True)
    partner_id = fields.Many2one(
        'res.partner', string='Bên giao', tracking=True)
    warehouse_id = fields.Many2one(
        'stock.warehouse', string='Kho nhận', required=True, tracking=True)
    date = fields.Date(string='Ngày kiểm', required=True, tracking=True,
                       default=fields.Date.context_today)
    inspector_id = fields.Many2one(
        'res.users', string='Người kiểm tra', required=True, tracking=True,
        default=lambda s: s.env.user)
    source = fields.Selection(
        [('po', 'Đơn mua hàng'),
         ('transfer', 'Điều chuyển từ kho khác'),
         ('handover', 'Bàn giao từ dự án'),
         ('other', 'Nguồn khác')],
        string='Nguồn hàng', required=True, default='po', tracking=True,
        help='Nguồn khác nhau thì hồ sơ đi kèm khác nhau, và người chịu '
             'trách nhiệm khi sai cũng khác.')
    origin = fields.Char(string='Chứng từ gốc')
    line_ids = fields.One2many(
        'eam.inbound.check.line', 'check_id', string='Dòng kiểm tra')
    attachment_ids = fields.Many2many(
        'ir.attachment', 'eam_inbound_check_att_rel', 'check_id', 'att_id',
        string='Chứng chỉ & hồ sơ đi kèm',
        help='Chứng chỉ xuất xưởng, phiếu thí nghiệm, CO/CQ. Thiếu hồ sơ '
             'cũng là một dạng sai lệch — đánh dấu ở dòng tương ứng.')
    co_sai_lech = fields.Boolean(
        string='Có sai lệch', compute='_compute_tong', store=True)
    so_dong_sai = fields.Integer(
        string='Số dòng sai lệch', compute='_compute_tong', store=True)
    state = fields.Selection(
        [('draft', 'Nháp'),
         ('done', 'Đã kiểm'),
         ('cancelled', 'Đã huỷ')],
        string='Trạng thái', default='draft', required=True, tracking=True,
        copy=False)
    note = fields.Text(string='Kết luận & ghi chú')
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda s: s.env.company)

    @api.depends('line_ids.qty_rejected', 'line_ids.ly_do_sai_lech')
    def _compute_tong(self):
        for r in self:
            sai = r.line_ids.filtered(
                lambda l: l.qty_rejected > 0 or l.ly_do_sai_lech)
            r.so_dong_sai = len(sai)
            r.co_sai_lech = bool(sai)

    @api.model_create_multi
    def create(self, vals_list):
        for v in vals_list:
            if v.get('name', _('Mới')) == _('Mới'):
                v['name'] = self.env['ir.sequence'].next_by_code(
                    'eam.inbound.check') or _('Mới')
        return super().create(vals_list)

    # ------------------------------------------------------------------
    @api.onchange('picking_id')
    def _onchange_picking(self):
        """Chép từ phiếu nhập sang, mặc định NHẬN BAO NHIÊU NGHIỆM THU
        BẤY NHIÊU — người kiểm chỉ phải sửa những dòng có vấn đề.

        Mặc định ngược lại (nghiệm thu 0) thì người ta gõ cho xong, và
        con số mất ý nghĩa.
        """
        for r in self:
            if not r.picking_id:
                continue
            r.partner_id = r.picking_id.partner_id
            r.origin = r.picking_id.name
            r.warehouse_id = r.picking_id.picking_type_id.warehouse_id
            dong = []
            for ml in r.picking_id.move_line_ids:
                dong.append((0, 0, {
                    'product_id': ml.product_id.id,
                    'lot_id': ml.lot_id.id if ml.lot_id else False,
                    'uom_id': ml.product_uom_id.id,
                    'qty_received': ml.quantity,
                    'qty_accepted': ml.quantity,
                }))
            r.line_ids = [(5, 0, 0)] + dong

    # ------------------------------------------------------------------
    def action_xac_nhan(self):
        """Hàng đạt về ô chứa, hàng không đạt vào Cách ly."""
        Move = self.env['stock.move']
        ML = self.env['stock.move.line']
        cho_kiem = self.env.ref('eam_stock.loc_cho_kiem_tra')
        cach_ly = self.env.ref('eam_stock.loc_cach_ly')
        for r in self:
            if r.state != 'draft':
                raise UserError(_('Phiếu "%s" đã kiểm rồi.', r.name))
            if not r.line_ids:
                raise UserError(_('Phiếu "%s" chưa có dòng nào.', r.name))
            for l in r.line_ids:
                if l.qty_accepted + l.qty_rejected > l.qty_received:
                    raise UserError(_(
                        'Dòng "%(sp)s": nghiệm thu %(dat)g + từ chối '
                        '%(tu)g vượt quá số đã nhận %(nhan)g.',
                        sp=l.product_id.display_name, dat=l.qty_accepted,
                        tu=l.qty_rejected, nhan=l.qty_received))
                if l.qty_rejected > 0 and not l.ly_do_sai_lech:
                    raise UserError(_(
                        'Dòng "%s" có hàng từ chối nhưng chưa khai lý do. '
                        'Không khai thì sáu tháng sau không ai trả lời '
                        'được nhà cung cấp này sai những gì.',
                        l.product_id.display_name))

                for sl, dich in ((l.qty_accepted, l.dest_location_id
                                  or r.warehouse_id.lot_stock_id),
                                 (l.qty_rejected, cach_ly)):
                    if sl <= 0:
                        continue
                    mv = Move.create({
                        'product_id': l.product_id.id,
                        'product_uom': l.uom_id.id,
                        'product_uom_qty': sl,
                        'location_id': cho_kiem.id,
                        'location_dest_id': dich.id,
                        'company_id': r.company_id.id,
                    })
                    mv._action_confirm()
                    mv.move_line_ids.unlink()
                    ML.create({
                        'move_id': mv.id, 'product_id': l.product_id.id,
                        'product_uom_id': l.uom_id.id, 'quantity': sl,
                        'lot_id': l.lot_id.id if l.lot_id else False,
                        'location_id': cho_kiem.id,
                        'location_dest_id': dich.id,
                        'company_id': r.company_id.id,
                    })
                    mv.picked = True
                    mv._action_done()
            r.state = 'done'
            if r.co_sai_lech:
                r.message_post(body=_(
                    '<b>Có sai lệch ở %(n)d dòng.</b> Hàng từ chối đã vào '
                    '<i>Cách ly</i> — chưa trả nhà cung cấp. Lập yêu cầu '
                    'xử lý với bên giao trước khi chuyển hàng đi.',
                    n=r.so_dong_sai))
        return True

    def action_huy(self):
        for r in self:
            if r.state == 'done':
                raise UserError(_(
                    'Phiếu "%s" đã kiểm xong và đã sinh phiếu kho — không '
                    'huỷ được. Nếu kiểm sai thì lập phiếu điều chỉnh tồn '
                    'kèm lý do.', r.name))
            r.state = 'cancelled'
        return True


class EamInboundCheckLine(models.Model):
    _name = 'eam.inbound.check.line'
    _description = 'Dòng kiểm tra đầu vào'
    _order = 'check_id, id'

    check_id = fields.Many2one(
        'eam.inbound.check', string='Phiếu kiểm', required=True,
        ondelete='cascade', index=True)
    product_id = fields.Many2one(
        'product.product', string='Vật tư', required=True)
    lot_id = fields.Many2one(
        'stock.lot', string='Sê-ri / lô',
        domain="[('product_id', '=', product_id)]")
    uom_id = fields.Many2one('uom.uom', string='Đơn vị')
    qty_ordered = fields.Float(string='SL đặt',
                               digits='Product Unit of Measure')
    qty_received = fields.Float(string='SL nhận', required=True,
                                digits='Product Unit of Measure')
    qty_accepted = fields.Float(string='SL nghiệm thu',
                                digits='Product Unit of Measure')
    qty_rejected = fields.Float(string='SL từ chối',
                                digits='Product Unit of Measure')
    ly_do_sai_lech = fields.Selection(
        LY_DO_SAI_LECH, string='Lý do sai lệch')
    dest_location_id = fields.Many2one(
        'stock.location', string='Về ô chứa',
        domain="[('usage', '=', 'internal'), ('eam_cam_xuat', '=', False)]",
        help='Bỏ trống thì về vị trí tồn mặc định của kho.')
    has_cert = fields.Boolean(string='Có chứng chỉ đi kèm')
    note = fields.Char(string='Ghi chú')
    company_id = fields.Many2one(related='check_id.company_id', store=True)

    @api.onchange('qty_received', 'qty_accepted')
    def _onchange_qty(self):
        """Phần không nghiệm thu mặc định là phần từ chối — nhưng vẫn cho
        sửa, vì có trường hợp hàng còn đang chờ kết luận."""
        for l in self:
            if l.qty_received and l.qty_accepted is not None:
                con = l.qty_received - l.qty_accepted
                if con >= 0 and not l.qty_rejected:
                    l.qty_rejected = con
