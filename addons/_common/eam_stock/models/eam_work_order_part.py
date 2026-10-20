# -*- coding: utf-8 -*-
"""Dòng vật tư trên lệnh công việc — ba số lượng, không phải một.

Một dòng vật tư đi qua ba mốc khác nhau, và gộp chúng vào một ô là nguồn
gốc của mọi sai lệch tồn kho:

* **Yêu cầu** (``qty``) — xin bao nhiêu. Đây là số dùng để GIỮ CHỖ.
* **Đã xuất** (``qty_xuat``) — kho đưa ra bao nhiêu.
* **Đã trả** (``qty_tra``) — mang về lại bao nhiêu.

``qty_dung = qty_xuat - qty_tra`` mới là số thật sự tiêu hao, và **đó là
số tính tiền**. Lấy ``qty`` tính tiền thì thợ xin 2 dùng 1 vẫn bị tính
tiền 2 — vừa sai chi phí lệnh, vừa sai tồn kho.
"""
from odoo import _, api, fields, models

TINH_TRANG_TRA = [
    ('kho', 'Còn tốt — về thẳng kho'),
    ('kiem', 'Cần kiểm tra trước khi dùng lại'),
    ('hong', 'Hỏng — không dùng lại được'),
]


class EamWorkOrderPart(models.Model):
    _inherit = 'eam.work.order.part'

    lot_id = fields.Many2one(
        'stock.lot', string='Sê-ri / lô',
        domain="[('product_id', '=', product_id)]",
        help='Bắt buộc với vật tư quay vòng. Hãng chỉ bảo hành con mang '
             'đúng số sê-ri này — để hệ thống tự chọn một con bất kỳ '
             'trong kho là vứt đi quyền đòi bảo hành.')
    move_id = fields.Many2one(
        'stock.move', string='Phiếu xuất', readonly=True, copy=False,
        ondelete='set null')
    move_tra_ids = fields.Many2many(
        'stock.move', 'eam_part_move_tra_rel', 'part_id', 'move_id',
        string='Phiếu hoàn trả', readonly=True, copy=False)

    trang_thai_kho = fields.Selection(
        [('chua', 'Chưa giữ chỗ'),
         ('giu', 'Đã giữ chỗ'),
         ('thieu', 'Giữ chỗ chưa đủ'),
         ('xuat', 'Đã xuất kho'),
         ('ngoai', 'Không qua kho')],
        string='Trạng thái kho', compute='_compute_trang_thai_kho',
        store=True)

    qty_xuat = fields.Float(
        string='Đã xuất', digits='Product Unit of Measure',
        compute='_compute_so_luong', store=True)
    qty_tra = fields.Float(
        string='Đã trả', digits='Product Unit of Measure',
        compute='_compute_so_luong', store=True)
    qty_dung = fields.Float(
        string='Đã dùng', digits='Product Unit of Measure',
        compute='_compute_so_luong', store=True,
        help='Đã xuất trừ đã trả. Đây là số tính tiền.')

    qty_tra_moi = fields.Float(
        string='Trả lại', digits='Product Unit of Measure',
        help='Số lượng mang về kho lần này. Bấm "Ghi nhận hoàn trả" trên '
             'lệnh để xử lý.')
    tinh_trang_tra = fields.Selection(
        TINH_TRANG_TRA, string='Tình trạng hàng trả', default='kho',
        help='Tháo khỏi máy KHÔNG có nghĩa là dùng lại được. Hàng cần '
             'kiểm tra hoặc đã hỏng đi vào vị trí riêng, không cộng vào '
             'tồn khả dụng cho tới khi có người xác nhận.')

    # --- hiện trạng kho tại nguồn xuất, để người khai nhìn thấy mà quyết ---
    ton_thuc_te = fields.Float(
        string='Tồn thực tế', compute='_compute_ton', digits='Product Unit of Measure')
    ton_giu_cho = fields.Float(
        string='Đang giữ chỗ', compute='_compute_ton', digits='Product Unit of Measure')
    ton_kha_dung = fields.Float(
        string='Khả dụng', compute='_compute_ton', digits='Product Unit of Measure')

    khong_qua_kho = fields.Boolean(
        string='Không qua kho',
        help='Vật tư mua thẳng cho chính việc này, hoặc hãng cấp theo bảo '
             'hành — chưa từng nằm trong kho nên không có gì để xuất.')

    # ------------------------------------------------------------------
    @api.depends('move_id.state', 'move_id.quantity',
                 'move_tra_ids.state', 'move_tra_ids.quantity')
    def _compute_so_luong(self):
        for l in self:
            xuat = (l.move_id.quantity
                    if l.move_id and l.move_id.state == 'done' else 0.0)
            tra = sum(m.quantity for m in l.move_tra_ids
                      if m.state == 'done')
            l.qty_xuat = xuat
            l.qty_tra = tra
            l.qty_dung = xuat - tra

    @api.depends('product_id', 'move_id.state', 'khong_qua_kho',
                 'move_id.quantity', 'qty')
    def _compute_trang_thai_kho(self):
        for l in self:
            if l.khong_qua_kho or not l.product_id:
                l.trang_thai_kho = 'ngoai'
            elif not l.move_id:
                l.trang_thai_kho = 'chua'
            elif l.move_id.state == 'done':
                l.trang_thai_kho = 'xuat'
            elif l.move_id.state == 'assigned':
                l.trang_thai_kho = 'giu'
            else:
                # confirmed / partially_available — giữ chỗ KHÔNG đủ.
                # Phải tách khỏi 'đã giữ chỗ': một dòng giữ được 1/5 mà
                # hiện là "đã giữ chỗ" thì tới hôm lên trụ mới biết thiếu.
                l.trang_thai_kho = 'thieu'

    @api.depends('product_id', 'order_id.stock_location_id')
    def _compute_ton(self):
        for l in self:
            kho = l.order_id.stock_location_id
            if not l.product_id or not kho:
                l.ton_thuc_te = l.ton_giu_cho = l.ton_kha_dung = 0.0
                continue
            p = l.product_id.with_context(location=kho.id)
            l.ton_thuc_te = p.qty_available
            l.ton_kha_dung = p.free_qty
            l.ton_giu_cho = p.qty_available - p.free_qty

    @api.onchange('product_id')
    def _onchange_product_lot(self):
        """Đổi vật tư thì sê-ri cũ không còn đúng — xoá đi.

        Giữ lại sê-ri của vật tư trước là cách êm ái nhất để xuất nhầm
        con khác: ô vẫn có chữ, trông như đã khai đúng.
        """
        for l in self:
            if l.lot_id and l.lot_id.product_id != l.product_id:
                l.lot_id = False

    # ------------------------------------------------------------------
    @api.depends('qty', 'unit_cost', 'is_warranty_part',
                 'qty_dung', 'move_id.state')
    def _compute_amount(self):
        """Chưa xuất thì tính theo số YÊU CẦU (dự trù); xuất rồi thì tính
        theo số ĐÃ DÙNG (thực tế).

        Hai giai đoạn hai cơ sở, và phải đổi đúng lúc: giữ nguyên số yêu
        cầu sau khi đã trả hàng thì chi phí lệnh vĩnh viễn cao hơn thực
        tế, mà không ô nào trên màn hình nói ra điều đó.
        """
        for l in self:
            if l.is_warranty_part:
                l.amount = 0.0
                continue
            co_so = (l.qty_dung if (l.move_id and l.move_id.state == 'done')
                     else (l.qty or 0.0))
            l.amount = co_so * (l.unit_cost or 0.0)
