# -*- coding: utf-8 -*-
{
    'name': 'Realty Project — Quản lý hiện trường (Site Management)',
    'version': '19.0.1.1.0',
    'category': 'Realty/Project',
    'summary': 'Nhật ký thi công, Punch list (lỗi & khắc phục), An toàn '
               'lao động (kiểm tra, toolbox meeting, sự cố) cho công trường.',
    'description': """
Realty Project — Quản lý hiện trường (rp_site)
==============================================

Phase 1 — 3 khối nghiệp vụ hiện trường, neo vào xương sống dự án
(hạng mục → HĐ nhà thầu → lịch thi công → BBNT):

1. **Nhật ký thi công** (hồ sơ bắt buộc theo NĐ 06/2021): thời tiết,
   nhân lực theo nhà thầu, máy móc thiết bị, công việc thực hiện (link
   task lịch thi công), vật tư, vướng mắc/chỉ đạo, ảnh hiện trường —
   luồng Lập → Trình → Xác nhận (TVGS/CĐT). Nhật ký là input cho
   Trợ lý AI đọc tiến độ.
2. **Punch list**: lỗi phát hiện tại hiện trường — vị trí, hạng mục,
   nhà thầu chịu trách nhiệm, mức độ, hạn khắc phục, vòng đời
   Mở → Đang xử lý → Đã khắc phục → Đóng (nghiệm thu lại).
3. **An toàn (HSE)**: biên bản kiểm tra an toàn (checklist), sổ
   toolbox meeting, sổ sự cố/near-miss.

Người nhập: kỹ sư hiện trường CĐT/tổng thầu (backend Odoo).
""",
    'author': 'BSDInsight',
    'website': 'https://bsdinsight.com',
    'license': 'LGPL-3',
    'depends': [
        'mail',
        'rp_contract',
        'rp_cost_base',
        'rp_schedule',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'views/rp_site_diary_views.xml',
        'views/rp_site_punch_views.xml',
        'views/rp_site_hse_views.xml',
        'views/rp_contract_views.xml',
        'views/rp_site_menus.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
