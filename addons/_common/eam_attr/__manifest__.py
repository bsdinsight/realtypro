# -*- coding: utf-8 -*-
{
    'name': 'EAMOne — Thông số kỹ thuật khai được theo nhóm',
    'version': '19.0.1.0.0',
    'category': 'EAMOne',
    'summary': 'Người dùng tự thêm thông số cho từng nhóm thiết bị — không '
               'cần lập trình, không cần nâng cấp module.',
    'description': """
EAMOne — Thông số kỹ thuật khai được theo nhóm
===============================================

Mỗi loại thiết bị có bộ thông số riêng. Máy biến áp cần điện áp sơ cấp,
thứ cấp và tổ đấu dây. Inverter cần công suất DC/AC và số MPPT. Tua-bin
cần đường kính rotor và chiều cao trục. Thêm một trường cho mỗi loại
nghĩa là mỗi khách mới lại phải sửa mã — và khách không chờ được.

Module này cho **nhóm tài sản giữ ĐỊNH NGHĨA, từng tài sản giữ GIÁ TRỊ**,
dùng đúng cơ chế Properties có sẵn của Odoo. Người dùng tự thêm ô ngay
trên giao diện: tên, kiểu dữ liệu, danh sách chọn.

Vì sao không tự dựng bảng thuộc tính
-------------------------------------
Lõi Odoo đã làm rồi, và tìm kiếm · lọc · gom nhóm · xuất báo cáo đều
hiểu nó sẵn. Bảng tự dựng phải viết lại từng thứ đó, và sẽ thiếu vài thứ
mà không ai nhận ra cho tới lúc khách cần.

Cố ý KHÔNG có trong module này
-------------------------------
Danh sách thông số cụ thể của từng loại thiết bị. Đó là **cấu hình của
khách**, không phải mã nguồn — nhà máy nào cũng khai khác nhau, và khai
cứng vào module là lặp lại đúng sai lầm của việc viết cứng số ngày trong
công thức. Module cấp cơ chế; dữ liệu khởi đầu nạp riêng và sửa được.
""",
    'author': 'BSD Insight',
    'website': 'https://bsdinsight.com',
    'license': 'LGPL-3',
    'depends': ['eam_core'],
    'data': [
        'views/eam_attr_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
