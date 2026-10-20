# -*- coding: utf-8 -*-
"""Di chuyển kho — nhớ nó sinh ra từ lệnh công việc nào."""
from odoo import api, fields, models


class StockMove(models.Model):
    _inherit = 'stock.move'

    eam_work_order_id = fields.Many2one(
        'eam.work.order', string='Lệnh công việc', index=True,
        ondelete='set null', copy=False,
        help='Lệnh đã lấy vật tư này. Là khoá ngoại thật chứ không phải '
             'chuỗi ghi chú, nên lọc được, thống kê được, và không hỏng '
             'khi lệnh đổi số hiệu.')

    # Odoo tính `reference` từ `picking_id.name`. Phiếu xuất cho bảo trì
    # cố ý KHÔNG bọc trong picking, nên nếu để nguyên thì cả cột Tham
    # chiếu trong lịch sử di chuyển vật tư sẽ TRỐNG — nhìn vào không biết
    # vật tư đi đâu, mà đó đúng là câu người giữ kho cần trả lời.
    #
    # Bẫy: viết lại một hàm tính có @api.depends thì danh sách phụ thuộc
    # MỚI thay thế danh sách cũ, không cộng dồn. Phải chép lại đủ phụ
    # thuộc của bản gốc, nếu không reference sẽ thôi cập nhật khi phiếu
    # kho hay phiếu kiểm kê đổi — hỏng im lặng ở chỗ chẳng liên quan gì
    # tới bảo trì.
    @api.depends('picking_id.name', 'scrap_id.name', 'location_dest_usage',
                 'is_inventory', 'inventory_name', 'eam_work_order_id.name')
    def _compute_reference(self):
        super()._compute_reference()
        for m in self:
            if not m.reference and m.eam_work_order_id:
                m.reference = m.eam_work_order_id.name
