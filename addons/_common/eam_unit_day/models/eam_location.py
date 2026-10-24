# -*- coding: utf-8 -*-
"""Vị trí nào là TỔ MÁY PHÁT ĐIỆN — khai, không đoán.

Vì sao không lấy "mọi vị trí thiết bị"
---------------------------------------
Cây vị trí của một nhà máy chứa cả thứ không phát điện: trạm khí tượng,
nhà điều hành, trạm biến áp. Đếm bừa "mọi vị trí thiết bị" là đưa trạm
khí tượng vào mẫu số — đúng cái đã dính ở khả dụng nhà máy điện mặt
trời: mười sáu bộ nghịch lưu thành mười bảy đơn vị, khả dụng tụt 6%, và
con số vẫn nằm trong khoảng 0–100% nên không ai nghi.

Nên có một cờ riêng. Và vì bắt người dùng tích tay hai mươi sáu ô là
cách chắc chắn để nó không bao giờ được khai, có sẵn một nút **gợi ý**:
vị trí nào có điểm đo điện năng thì gần như chắc chắn là tổ máy. Nút ấy
ĐỀ XUẤT rồi báo đã làm gì — người xác nhận, máy không tự quyết.
"""
from odoo import _, api, fields, models


class EamLocation(models.Model):
    _inherit = 'eam.location'

    la_to_may = fields.Boolean(
        string='Là tổ máy phát điện', index=True,
        help='Tua-bin, bộ nghịch lưu — thứ thật sự phát ra điện. Trạm khí '
             'tượng và nhà điều hành thì KHÔNG, dù chúng cũng là vị trí '
             'thiết bị. Cờ này quyết định bảng hiệu suất tổ máy có bao '
             'nhiêu dòng, và mẫu số khả dụng có bao nhiêu đơn vị.')
    unit_day_ids = fields.One2many(
        'eam.unit.day', 'location_id', string='Hiệu suất theo ngày')

    def cong_suat_dinh_muc_kw(self):
        """Công suất định mức của tổ máy, kèm chỗ lấy số.

        Ba nguồn, theo thứ tự chắc chắn giảm dần. Không có nguồn nào thì
        trả về ``None`` — KHÔNG trả 0. Hệ số công suất chia cho 0 ra vô
        nghĩa, mà chia cho một con số đoán bừa thì ra một tỷ lệ trông
        hợp lý và sai.
        """
        self.ensure_one()
        if self.power_curve_id and self.power_curve_id.rated_kw:
            return (self.power_curve_id.rated_kw,
                    _('đường cong công suất "%s"',
                      self.power_curve_id.display_name))
        # Sổ tài sản ghi model bằng CHỮ (model_ref), không trỏ sang
        # danh mục model thiết bị — nên tra công suất định mức qua đó
        # phải khớp theo tên, và khớp theo tên là chỗ sai thầm lặng.
        # Bỏ hẳn nhánh ấy: thà nói "chưa khai" còn hơn khớp nhầm.
        if self.rated_power_mw:
            return (self.rated_power_mw * 1000.0,
                    _('công suất đặt khai trên vị trí'))
        return None, ''

    def to_may(self):
        """Các tổ máy thuộc nhà máy này, theo cờ đã KHAI."""
        self.ensure_one()
        return self.env['eam.location'].search(
            [('id', 'child_of', self.id), ('la_to_may', '=', True)],
            order='code')

    def action_danh_dau_to_may(self):
        """Gợi ý: vị trí có điểm đo ĐIỆN NĂNG thì là tổ máy.

        Đề xuất rồi báo đã làm gì — không tự quyết trong im lặng. Vị trí
        đã tích tay thì giữ nguyên.
        """
        T = self.env['eam.tag']
        them = bo_qua = 0
        for nm in self:
            for vt in self.env['eam.location'].search([
                    ('id', 'child_of', nm.id),
                    ('location_type', '=', 'position')]):
                co = T.search_count([
                    ('location_id', 'child_of', vt.id),
                    ('tag_type', '=', 'energy'),
                    ('is_virtual', '=', False)])
                if co and not vt.la_to_may:
                    vt.la_to_may = True
                    them += 1
                elif not co and not vt.la_to_may:
                    bo_qua += 1
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {
                'type': 'info', 'sticky': False,
                'message': _(
                    'Đánh dấu %(a)d vị trí là tổ máy (có điểm đo điện '
                    'năng). Bỏ qua %(b)d vị trí không có điểm đo điện '
                    'năng — soi lại nếu trong đó có tổ máy chưa gắn đồng '
                    'hồ.', a=them, b=bo_qua)},
        }

    def kiem_so_to_may(self):
        """So số tổ máy đã khai với số đơn vị dùng cho mẫu số khả dụng.

        Hai con số này nói cùng một chuyện, nên lệch là có chỗ khai sai —
        và hệ NÓI RA chứ không chọn hộ một trong hai.
        """
        self.ensure_one()
        n = len(self.to_may())
        khai = self.so_don_vi_kha_dung or 0
        if khai and n and khai != n:
            return _(
                'Đã khai %(a)d tổ máy, nhưng mẫu số khả dụng đang dùng '
                '%(b)d đơn vị. Hai con số này nói cùng một chuyện — lệch '
                'nghĩa là một trong hai khai sai.', a=n, b=khai)
        return ''
