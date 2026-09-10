# -*- coding: utf-8 -*-
"""Cấu hình phân hệ Vay & Khế ước.

Hiện chỉ có một tham số: NGƯỠNG NET-OFF. Trước đây ngưỡng này là
hằng số 100.000 ₫ nằm trong mã, nghĩa là muốn đổi phải sửa mã và
deploy. Mỗi doanh nghiệp lại có mức chênh lệch lẻ chấp nhận được
khác nhau — chỗ thì vài trăm đồng, chỗ thì cả triệu — nên nó thuộc
về cấu hình chứ không phải mã.

*** Vì sao KHÔNG dùng config_parameter= của Odoo ***
Cơ chế sẵn có của res.config.settings quy đổi giá trị 0 thành False
rồi XOÁ tham số (xem ResConfigSettings.set_values), nên "đặt ngưỡng
= 0" và "chưa cấu hình bao giờ" trở thành cùng một trạng thái. Ở đây
hai thứ đó phải khác nhau: 0 nghĩa là CẤM net-off, chưa cấu hình
nghĩa là dùng mặc định cũ. Vì vậy đọc/ghi tham số thủ công.
"""
from odoo import api, fields, models

# Giữ nguyên con số cũ làm mặc định: DB đang chạy không đổi hành vi
# sau khi nâng cấp, chỉ là từ nay sửa được.
DEFAULT_NET_OFF_THRESHOLD = 100_000.0
PARAM_NET_OFF_THRESHOLD = 're_loan.net_off_threshold'


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    re_loan_net_off_threshold = fields.Float(
        string='Chênh lệch tối đa được net-off (₫)',
        digits=(16, 0),
        help='Số tiền chênh lệch lẻ tối đa mà kế toán được phép bù '
             'trừ thẳng trên một kỳ lịch lãi (nút "Net-off chênh '
             'lệch"). Chênh lệch vượt ngưỡng này bắt buộc phải tạo '
             'trả nợ chính thức để có vết kiểm toán. Đặt 0 để cấm '
             'net-off hoàn toàn.')

    @api.model
    def get_net_off_threshold(self):
        """Ngưỡng đang hiệu lực, dùng chung cho mọi chỗ cần kiểm."""
        raw = self.env['ir.config_parameter'].sudo().get_param(
            PARAM_NET_OFF_THRESHOLD)
        if raw in (None, False, ''):
            return DEFAULT_NET_OFF_THRESHOLD
        try:
            return float(raw)
        except (TypeError, ValueError):
            # Ai đó sửa tay tham số thành chuỗi rác — thà quay về mặc
            # định còn hơn để nút net-off nổ giữa lúc đối chiếu.
            return DEFAULT_NET_OFF_THRESHOLD

    @api.model
    def get_values(self):
        res = super().get_values()
        res['re_loan_net_off_threshold'] = self.get_net_off_threshold()
        return res

    def set_values(self):
        res = super().set_values()
        self.env['ir.config_parameter'].sudo().set_param(
            PARAM_NET_OFF_THRESHOLD,
            repr(max(0.0, self.re_loan_net_off_threshold or 0.0)))
        return res
