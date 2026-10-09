# -*- coding: utf-8 -*-
{
    'name': 'Hồ sơ sản phẩm (ẩn menu dòng không dùng)',
    'version': '19.0.1.0.0',
    'category': 'Technical',
    'summary': 'Một tham số cho biết bản triển khai này thuộc dòng sản '
               'phẩm nào, và ẩn menu gốc của các dòng còn lại.',
    'description': """
Hồ sơ sản phẩm
==============

Cùng một bộ mã phục vụ nhiều dòng sản phẩm — EPC, CRM, bán hàng, vận
hành, tài sản. Mỗi khách chỉ dùng một hoặc vài dòng, nhưng menu gốc của
TẤT CẢ các dòng đã cài đều hiện ra. Khách EPC mở hệ thống lên thấy
"Bất động sản" với toà nhà, tầng, căn hộ — những thứ nhà máy điện gió
không bao giờ có.

Module này giữ đúng MỘT tham số: *bản triển khai này thuộc hồ sơ nào*.
Từ đó lọc menu gốc lúc dựng.

Ẩn, không gỡ
------------
Không gỡ module, không xoá dữ liệu, không đụng vào bản ghi menu. Mọi
liên kết, báo cáo, quyền hạn vẫn chạy y nguyên — chỉ là người dùng
không phải nhìn nhánh họ không dùng. Đổi về "Đầy đủ" là hiện lại ngay.

Vì sao không đặt ``active = False`` lên menu
--------------------------------------------
Đó là cách nhanh nhất, và hỏng ở ba chỗ khi có nhiều bản triển khai:
không ai biết vì sao menu biến mất; mỗi tenant mới lại phải nhớ sửa tay;
và nó trộn *dữ liệu* (cờ active) với *quyết định triển khai* ("khách này
không dùng dòng bất động sản").

Vì sao không gắn cứng trong mã
------------------------------
Có khách chạy NHIỀU dòng trên cùng một cơ sở dữ liệu — vừa thi công dự
án vừa bán căn hộ. Gắn cứng vào module là ẩn cho tất cả mọi người, kể cả
họ. Nên đây là tham số của từng bản triển khai.

Hai chi tiết dễ bỏ sót
----------------------
* ``load_menus_root`` (danh sách ứng dụng) **không** đi qua blacklist của
  ``load_menus``. Chặn một chỗ thì menu mất ở thanh trên mà vẫn còn
  trong danh sách ứng dụng — nên phải chặn cả ``get_user_roots``.
* Hai hàm đó đều bọc ``ormcache``, và Odoo chỉ xoá cache khi bản ghi
  ``ir.ui.menu`` bị ghi. Ở đây ta chỉ đổi một tham số, nên phải tự xoá
  cache lúc lưu — thiếu thì bấm Lưu xong không thấy gì đổi.
""",
    'author': 'BSD Insight',
    'website': 'https://bsdinsight.com',
    'license': 'AGPL-3',
    'depends': ['base'],
    'data': ['views/res_config_settings_views.xml'],
    'installable': True,
}
