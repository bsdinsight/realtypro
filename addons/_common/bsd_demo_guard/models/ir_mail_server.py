# -*- coding: utf-8 -*-
"""Chặn mọi thư gửi ra ngoài của bản demo.

CHẶN Ở ``send_email`` vì đây là cửa ra DUY NHẤT tới máy chủ SMTP: thư
từ hàng đợi, thư gửi ngay (``force_send``), thư đặt lại mật khẩu đều đi
qua đây. Không có máy chủ thư nào khai trong DB thì Odoo vẫn thử
``localhost:25`` — và DB demo nằm cùng máy chủ PostgreSQL với các stack
khác, nên cron gửi thư có thể do một container KHÁC chạy (container
tenants quét mọi DB). Chặn trong mã của module thì chạy ở container nào
cũng như nhau.

Trả về Message-Id như gửi thành công thay vì ném lỗi: khách bấm "Gửi"
trên báo giá thì thấy thao tác chạy trọn và thư vào lịch sử trao đổi —
đúng điều họ muốn xem — chỉ là không có gì rời máy chủ.
"""
import logging

from odoo import models

_logger = logging.getLogger(__name__)

PARAM_BLOCK = 'bsd_demo_guard.block_outgoing_mail'


class IrMailServer(models.Model):
    _inherit = 'ir.mail_server'

    def send_email(self, message, *args, **kwargs):
        blocked = self.env['ir.config_parameter'].sudo().get_param(
            PARAM_BLOCK) in ('1', 'True', 'true')
        if not blocked:
            return super().send_email(message, *args, **kwargs)
        _logger.info(
            'bsd_demo_guard: KHÔNG gửi thư "%s" tới %s (bản demo chặn thư '
            'ra ngoài).', message.get('Subject'), message.get('To'))
        return message.get('Message-Id') or 'bsd-demo-blocked'
