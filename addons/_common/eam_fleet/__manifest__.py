# -*- coding: utf-8 -*-
{
    'name': 'EAMOne — Tổng quan toàn danh mục',
    'version': '19.0.1.0.0',
    'category': 'EAMOne',
    'summary': 'Màn người quản lý O&M mở mỗi sáng: nhà máy nào đang kéo '
               'cả đội xuống.',
    'description': """
Tổng quan toàn danh mục nhà máy
===============================

Mọi màn khác của EAMOne trả lời cho MỘT nhà máy hoặc MỘT chiều. Màn này
trả lời câu của người quản lý nhiều nhà máy: **nhà máy nào đang kéo cả
đội xuống**.

Bốn khối, theo đúng thứ tự người ta hỏi:

1. **Đội máy** — sản lượng ngày, khả dụng tháng, doanh thu luỹ kế.
2. **Từng nhà máy** — một dòng một nhà máy, kèm MẪU SỐ của mọi tỷ lệ.
3. **Việc phải làm** — cảnh báo, lệnh quá hạn, bảo trì tới hạn. Bấm
   vào là sang đúng danh sách.
4. **Số có tin được không** — dòng chưa đo được, giờ dừng chưa quy
   trách nhiệm, ngày thiếu dữ liệu.

Khối thứ tư là khối đáng giữ nhất. Mọi dashboard đều khoe ba khối đầu;
khối thứ tư là thứ phân biệt một sản phẩm biết mình đang đo gì với một
sản phẩm chỉ tô màu. Ba con số trong đó đều làm cho các con số phía
TRÊN đẹp hơn thực tế, nên giấu đi là tự lừa mình.

Dùng khuôn chung ``eam_dashboard``: không khai lại màu, không khai lại
SCSS. Xem ``eam_dashboard/KHUON.md``.
""",
    'author': 'BSD Insight',
    'website': 'https://realtypro.vn',
    'license': 'LGPL-3',
    'depends': [
        'eam_dashboard',
        'eam_energy_period',
        'eam_unit_day',
        'eam_solar',
        'eam_loss',
        'eam_alarm',
        'eam_work_order',
        'eam_pm',
    ],
    'data': ['views/eam_fleet_views.xml'],
    'assets': {
        'web.assets_backend': [
            'eam_fleet/static/src/js/eam_fleet.js',
            'eam_fleet/static/src/xml/eam_fleet.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
