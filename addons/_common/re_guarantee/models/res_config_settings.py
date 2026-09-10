# -*- coding: utf-8 -*-
"""Cấu hình nhắc bảo lãnh sắp hết hạn.

Hai tham số này vốn chỉ nằm ở Cấu hình > Kỹ thuật > Tham số hệ thống —
chỗ mà người theo dõi bảo lãnh không có quyền vào, và cũng không ai
nghĩ tới khi đi tìm "cấu hình nhắc trước bao nhiêu ngày" (backlog 760).
Đưa lên màn hình cấu hình của phân hệ.
"""
from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo import _

DEFAULT_LEAD_DAYS = 30
DEFAULT_REPEAT_DAYS = 7


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    re_guarantee_expiry_lead_days = fields.Integer(
        string='Nhắc trước (ngày)',
        config_parameter='re_guarantee.expiry_lead_days',
        default=DEFAULT_LEAD_DAYS,
        help='Bắt đầu gửi thư nhắc khi chứng thư còn bao nhiêu ngày là '
             'hết hạn. Để 0 thì dùng mặc định %s ngày.'
             % DEFAULT_LEAD_DAYS)
    re_guarantee_expiry_repeat_days = fields.Integer(
        string='Nhắc lặp lại sau (ngày)',
        config_parameter='re_guarantee.expiry_repeat_days',
        default=DEFAULT_REPEAT_DAYS,
        help='Đã nhắc rồi thì bao nhiêu ngày sau nhắc lại, chừng nào '
             'chứng thư chưa được xử lý. Để 0 thì dùng mặc định %s '
             'ngày.' % DEFAULT_REPEAT_DAYS)

    @api.constrains('re_guarantee_expiry_lead_days',
                    're_guarantee_expiry_repeat_days')
    def _check_expiry_days(self):
        for wiz in self:
            if wiz.re_guarantee_expiry_lead_days < 0 \
                    or wiz.re_guarantee_expiry_repeat_days < 0:
                raise ValidationError(_(
                    'Số ngày nhắc không được âm.'))
            if wiz.re_guarantee_expiry_lead_days > 365:
                raise ValidationError(_(
                    'Nhắc trước quá 365 ngày thì thư nhắc mất ý nghĩa — '
                    'chứng thư nào cũng "sắp hết hạn".'))
