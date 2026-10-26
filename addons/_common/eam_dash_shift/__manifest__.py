# -*- coding: utf-8 -*-
{
    'name': 'EAMOne — Bảng điều khiển ca trực',
    'version': '19.0.1.0.0',
    'category': 'EAMOne',
    'summary': 'Màn người trực mở đầu tiên mỗi sáng: hôm qua trại chạy '
               'thế nào, và hôm nay phải làm gì trước.',
    'description': """
Ca trực sáng nay
================

Trả lời ĐÚNG MỘT câu: *sáng nay tôi phải làm gì trước*. Không phải bản
tóm tắt tháng, không phải báo cáo cho lãnh đạo — hai thứ đó đọc theo
nhịp khác và nằm ở màn *Toàn danh mục nhà máy*.

Ba tầng, theo đúng thứ tự người trực cần:

1. **Hôm qua trại chạy thế nào** — sản lượng, khả dụng, hệ số công
   suất, PR.
2. **Việc phải làm hôm nay** — xếp theo mức gấp, bấm một dòng là mở
   thẳng danh sách đã lọc sẵn.
3. **Từng tổ máy** — máy nào đang kéo cả trại xuống.

Phong cách lấy từ khuôn dùng chung ``eam_dashboard``; module này KHÔNG
khai lại SCSS và không gõ mã màu. Xem ``eam_dashboard/KHUON.md``.

Hai luật của khuôn được áp ngay ở TẦNG DỮ LIỆU, không để giao diện tự
xoay xở: mọi con số đi kèm cờ ``do_duoc`` để "chưa đo được" không bao
giờ hoá thành số 0, và mọi tỷ lệ trả kèm mẫu số.
""",
    'author': 'BSD Insight',
    'website': 'https://realtypro.vn',
    'license': 'LGPL-3',
    'depends': [
        'eam_dashboard',
        'eam_unit_day',
        'eam_alarm',
        'eam_work_order',
        'eam_pm',
        'eam_daily_report',
    ],
    'data': [
        'views/eam_dash_shift_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'eam_dash_shift/static/src/js/eam_dash_shift.js',
            'eam_dash_shift/static/src/xml/eam_dash_shift.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
