# -*- coding: utf-8 -*-
{
    'name': 'Realty — Bridge Thuê tài sản ↔ Dashboard Vay',
    'version': '19.0.1.0.0',
    'category': 'Realty/Lease',
    'summary': 'Hiện dư nợ thuê tài chính trên dashboard Quản lý Vay — '
               'bức tranh tổng nghĩa vụ tín dụng.',
    'description': """
Glue module (auto_install khi có cả re_lease + re_loan_dashboard):
thêm nhóm "Thuê tài chính (tham khảo)" vào dashboard Quản lý Vay —
dư nợ gốc thuê TC + kỳ thuê đến hạn 30 ngày. Giữ re_lease độc lập
với Quản lý Vay (quyết định kiến trúc CC1).
""",
    'author': 'BSDInsight',
    'website': 'https://bsdinsight.com',
    'license': 'LGPL-3',
    'depends': ['re_lease', 're_loan_dashboard'],
    'data': ['views/re_loan_dashboard_views.xml'],
    'auto_install': True,
    'installable': True,
}
