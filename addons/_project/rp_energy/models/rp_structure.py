# -*- coding: utf-8 -*-
from odoo import fields, models


class RpStructure(models.Model):
    _inherit = 'rp.structure'

    # Hạng mục của nhà máy điện. Danh sách gốc là của dự án nhà ở (tháp
    # căn hộ, biệt thự, mặt dựng…), không có chỗ nào khai được một dãy
    # tua-bin hay một trạm nâng áp.
    structure_type = fields.Selection(
        selection_add=[
            ('wtg', 'Tua-bin gió (WTG)'),
            ('solar_array', 'Dàn pin mặt trời'),
            ('substation', 'Trạm nâng áp'),
            ('transmission', 'Đường dây / cáp ngầm'),
            ('bess_unit', 'Cụm lưu trữ pin'),
        ],
        ondelete={'wtg': 'set default', 'solar_array': 'set default',
                  'substation': 'set default', 'transmission': 'set default',
                  'bess_unit': 'set default'},
    )
