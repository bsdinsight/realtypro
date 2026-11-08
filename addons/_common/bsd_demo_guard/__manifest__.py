# -*- coding: utf-8 -*-
{
    'name': 'BSD — Khoá an toàn cho bản demo công khai',
    'version': '19.0.1.0.0',
    'category': 'Hidden',
    'summary': 'Tài khoản demo dùng chung không bị khách đổi mật khẩu hay '
               'bật 2FA; chặn mọi thư gửi ra ngoài.',
    'description': """
Khoá an toàn cho bản demo công khai
===================================

Bản demo mở công khai với tài khoản dùng chung (demo / demo) và KHÔNG
đặt lại hằng đêm có hai lỗ mà quyền hạn Odoo không bịt được:

1. **Người dùng nào cũng tự đổi được mật khẩu và tự bật xác thực hai
   lớp cho chính mình** — kể cả khi không có quyền quản trị. Khách đầu
   tiên làm một trong hai việc đó là mọi người sau bị khoá ngoài.
2. **Thư gửi ra ngoài mang tên miền của BSD**: khách bấm "Gửi email"
   trên một báo giá là thư đi thật tới địa chỉ họ gõ.

Module này **không làm gì** cho tới khi DB khai tham số hệ thống, nên
cài ở bất kỳ DB nào cũng vô hại:

* ``bsd_demo_guard.locked_logins`` — danh sách tên đăng nhập bị khoá,
  cách nhau dấu phẩy (ví dụ ``demo``). Chính người dùng đó không đổi
  được mật khẩu, không bật được 2FA. Quản trị viên vẫn đổi được hộ.
* ``bsd_demo_guard.block_outgoing_mail`` — đặt ``1`` thì không thư nào
  rời máy chủ; thư vẫn được tạo và ghi vào lịch sử như bình thường.
""",
    'author': 'BSDInsight',
    'website': 'https://bsdinsight.com',
    'license': 'LGPL-3',
    'depends': ['base', 'auth_totp'],
    'data': [],
    'installable': True,
    'application': False,
    'auto_install': False,
}
