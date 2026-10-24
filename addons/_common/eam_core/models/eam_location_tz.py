# -*- coding: utf-8 -*-
"""Múi giờ của nhà máy — biên NGÀY thuộc về nhà máy, không thuộc người xem.

"Ngày 15/10" của nhà máy là 00:00 tới 24:00 **giờ tại nhà máy**. Nếu
biên ngày lấy theo múi giờ của người đang mở màn hình thì cùng một tờ
báo cáo cho ra số khác nhau tuỳ ai bấm nút — một người ở Hà Nội và một
người ở Viêng Chăn rót lại cùng một tờ sẽ ra hai bộ số, và không có gì
báo.

Chuyện này không phải giả định: trong hệ đã có nhà máy ở Lào. Nên múi
giờ là **thuộc tính của nhà máy**, khai một lần, và tờ báo cáo CHỤP LẠI
múi giờ nó đã dùng — để sau còn biết con số đó đo trong khung giờ nào.
"""
import pytz

from odoo import fields, models


class EamLocation(models.Model):
    _inherit = 'eam.location'

    tz = fields.Selection(
        '_tz_get', string='Múi giờ nhà máy',
        help='Biên ngày của mọi báo cáo ngày lấy theo múi giờ này. Để '
             'trống thì dùng múi giờ của công ty, rồi tới Asia/'
             'Ho_Chi_Minh — nhưng khai rõ vẫn hơn, nhất là khi có nhà '
             'máy ngoài Việt Nam.')

    def _tz_get(self):
        # Odoo 19 KHÔNG có res.partner._tz_get — đó là hàm cấp module
        # trong addons/base, không phải phương thức của model. Gọi nó
        # như phương thức thì chỉ vỡ lúc dựng danh sách chọn, tức là
        # lúc MỞ FORM trên trình duyệt, chứ không vỡ lúc nạp module.
        return [(t, t) for t in sorted(
            pytz.all_timezones,
            key=lambda z: z if not z.startswith('Etc/') else '_' + z)]

    def mui_gio(self):
        """Múi giờ dùng cho biên ngày, theo thứ tự chắc chắn giảm dần."""
        self.ensure_one()
        nm = self if self.location_type == 'plant' else self.plant_id
        return (nm.tz or self.env.company.partner_id.tz
                or 'Asia/Ho_Chi_Minh')
