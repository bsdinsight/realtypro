# -*- coding: utf-8 -*-
{
    'name': 'Realty Loan — Dashboard',
    'version': '19.0.1.0.0',
    'category': 'Realty/Loan',
    'summary': 'Dashboard KPI cho Quản lý Vay — HĐTD, KW, Bảo lãnh, '
               'pending workflow, cảnh báo. Override menu top "Quản lý '
               'Vay" để mở dashboard này TRƯỚC submenu.',
    'description': """
Realty Loan — Dashboard (re_loan_dashboard)
============================================

TransientModel `re.loan.dashboard` tổng hợp KPI Quản lý Vay với 6 nhóm:

1. **HĐTD** — số active, tổng hạn mức, đã cấp facility, còn lại
2. **Facility (Hạn mức)** — split cho vay vs bảo lãnh (limit/used/avail)
3. **KW (Khế ước)** — active, dư nợ gốc, lãi đã trả YTD, sắp đáo hạn 30d
4. **Bảo lãnh** — outstanding, sắp hết hạn 30d
5. **Pending workflow** — giải ngân chờ duyệt, trích thu, BL request
6. **⚠ Cảnh báo** — KW quá hạn, BL hết hạn, lãi quá hạn

Click smart-button → drill-down list view filter sẵn.

Override `re_loan.menu_re_loan_root` set action=dashboard → user click
menu "Quản lý Vay" vào dashboard TRƯỚC khi xem submenu.
""",
    'author': 'BSD Insight',
    'website': 'https://bsdinsight.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        're_loan',
        're_guarantee',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/re_loan_dashboard_views.xml',
        'views/re_loan_menu_override.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
