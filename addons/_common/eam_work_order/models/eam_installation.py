# -*- coding: utf-8 -*-
"""Sổ lắp đặt đổi thì lệnh công việc phải suy lại thiết bị.

``eam.work.order.asset_id`` là trường TÍNH CÓ LƯU, nhưng ``@api.depends``
của nó chỉ liệt kê trường của CHÍNH cái lệnh — vị trí và hai ô ngày. Sổ
lắp đặt nằm ở bảng khác, nên ghi lắp đặt SAU khi lệnh đã tạo thì không
lệnh nào tính lại: ô thiết bị trống vĩnh viễn.

Và trống thì trông y hệt một câu hoàn toàn hợp lệ — *"việc này không gắn
máy nào"*, đúng với lệnh cấp nhà máy, với việc đường, mương cáp, móng.
Hai tình huống ngược nhau, cùng một ô rỗng, không ai phân biệt được.

CHỈ suy lại lệnh đang để TRỐNG
-------------------------------
``asset_id`` cho phép sửa tay — chỉ đích danh một cấu phần khác thay vì
cái máy chính ở vị trí đó. Tính lại hàng loạt là xoá lựa chọn có chủ ý
của người dùng mà không báo một tiếng, tệ hơn hẳn việc để nguyên một ô
cũ. Nên chỉ chạm vào ô rỗng.

Xoá bản ghi lắp đặt thì KHÔNG xử lý ở đây: khi đó ô thiết bị không
trống mà SAI, và sửa một ô sai đụng đúng ranh giới với lựa chọn tay nói
trên. Để nguyên và nhìn thấy được vẫn hơn là âm thầm ghi đè.
"""
from odoo import api, models


class EamInstallation(models.Model):
    _inherit = 'eam.installation'

    #: Ô nào của sổ lắp đặt đổi thì phép suy mới đổi theo.
    _ANH_HUONG = {'location_id', 'asset_id', 'date_install', 'date_remove'}

    def _suy_lai_lenh(self, them_vi_tri=None):
        vt = set(self.mapped('location_id').ids) | set(them_vi_tri or ())
        if not vt:
            return
        lenh = self.env['eam.work.order'].search([
            ('location_id', 'in', list(vt)),
            ('asset_id', '=', False),
        ])
        if lenh:
            # Báo cho ORM rằng đầu vào của phép suy đã đổi, thay vì gọi
            # thẳng hàm tính: gọi thẳng thì bỏ qua cơ chế phụ thuộc và
            # những trường ăn theo `asset_id` (loại cấu phần...) không
            # được tính lại.
            lenh.modified(['location_id'])

    @api.model_create_multi
    def create(self, vals_list):
        ban_ghi = super().create(vals_list)
        ban_ghi._suy_lai_lenh()
        return ban_ghi

    def write(self, vals):
        # Vị trí CŨ cũng phải quét: dời một lần lắp sang vị trí khác thì
        # lệnh ở chỗ cũ mất căn cứ, mà chỗ cũ không còn trong `self` sau
        # khi ghi.
        cu = set(self.mapped('location_id').ids)
        kq = super().write(vals)
        if self._ANH_HUONG & set(vals):
            self._suy_lai_lenh(cu)
        return kq
