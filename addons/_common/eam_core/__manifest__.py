# -*- coding: utf-8 -*-
{
    'name': 'EAMOne — Lõi tài sản & bảo trì',
    'version': '19.0.1.0.0',
    'category': 'EAMOne',
    'summary': 'Vị trí chức năng, tài sản mang sê-ri, lịch sử lắp đặt '
               'không chồng thời gian.',
    'description': """
EAMOne Core
===========

Lõi KHÔNG BIẾT GÌ về điện gió, và cũng không biết gì về EPCOne.
Đó là chủ ý: nội dung chuyên ngành nằm ở gói ngành (Wind Pack), còn mọi
thứ riêng của một khách nằm ở cấu hình. Lõi mà biết tên một khách hàng
là lúc sản phẩm bắt đầu hỏng.

Quyết định mô hình quan trọng nhất
----------------------------------
**Vị trí chức năng ≠ Thiết bị mang sê-ri.** `WTG-07 / vị trí hộp số` là
một chỗ; con hộp số mang sê-ri là một vật. Trong 25 năm, vật được tháo
ra, đem đi đại tu, rồi lắp sang chỗ khác.

Gộp hai thứ làm một thì mất hai câu hỏi đắt nhất:

* *"Vị trí 7 hỏng hộp số mấy lần?"* → lỗi nền móng, lỗi dòng gió, lỗi lắp
* *"Con hộp số này đã hỏng ở mấy vị trí?"* → lỗi lô hàng, lỗi thiết kế

Đây cũng là lý do KHÔNG dựng trên `maintenance.equipment` của Odoo: mô
hình đó phẳng, không có vị trí chức năng, không có lịch sử lắp đặt.

Ràng buộc chịu lực
------------------
Lịch sử lắp đặt **không được chồng thời gian** — trên cùng một vị trí, và
trên cùng một tài sản. Thiếu ràng buộc này thì sau vài năm lịch sử trở
thành vô nghĩa mà không ai phát hiện: hai con hộp số cùng "đang nằm" ở
một vị trí, hoặc một con "đang nằm" ở hai nơi.
""",
    'author': 'BSD Insight',
    'website': 'https://bsdinsight.com',
    'license': 'AGPL-3',
    'depends': ['base', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'data/eam_sequence_data.xml',
        'views/eam_asset_category_views.xml',
        'views/eam_structure_template_views.xml',
        'views/eam_location_views.xml',
        'views/eam_asset_views.xml',
        'views/eam_installation_views.xml',
        'views/eam_time_category_views.xml',
        'views/eam_outage_views.xml',
        'views/eam_menus.xml',
    ],
    'application': True,
    'installable': True,
}
