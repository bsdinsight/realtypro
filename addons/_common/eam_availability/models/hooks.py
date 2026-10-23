# -*- coding: utf-8 -*-
"""Tính lại cờ "đo được" của các cam kết đã có sẵn.

``do_duoc`` và ``ly_do_chua_do`` là trường tính CÓ LƯU. Module này bịt
lỗ hổng bằng cách kế thừa phương thức quyết định cờ đó — nhưng Odoo
không biết mã vừa đổi, nên bản ghi cũ **giữ nguyên "chưa đo được"**
trong khi phép đo đã chạy được.

Hậu quả thật: màn hợp đồng nói cam kết chưa đo được, còn kỳ đánh giá lại
ra số — hai chỗ nói hai chuyện, và người dùng tin chỗ nào cũng sai một
nửa. Đã dính đúng lỗi này ở hạn nghĩa vụ và ở tổn thất bậc thang, nên
lần này gọi tính lại ngay lúc cài.
"""


def post_init_hook(env):
    cam = env['eam.om.commitment'].search([])
    if cam:
        cam._compute_do_duoc()
        cam.flush_recordset()
