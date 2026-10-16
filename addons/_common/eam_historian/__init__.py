# -*- coding: utf-8 -*-
from . import models
from . import controllers


def post_init_hook(env):
    """Dựng bảng chuỗi thời gian và phân mảnh ngay khi cài.

    Bảng này KHÔNG do ORM quản nên Odoo không tự tạo — phải gọi tay ở
    đây. Không gọi thì lượt nạp đầu tiên mới tạo, tức là người dùng gặp
    một độ trễ khó hiểu đúng lúc đang thử kết nối SCADA.
    """
    env['eam.historian']._cron_phan_manh_truoc()
