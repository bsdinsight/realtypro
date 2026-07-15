# -*- coding: utf-8 -*-
{
    'name': 'Realty Project — Xây dựng',
    'version': '19.0.1.1.0',
    'category': 'Realty/Project',
    'summary': 'Menu Xây dựng hợp nhất: Dashboard thi công, Lịch thi công, '
               'Tiến độ, Hiện trường, RFI & Trình duyệt, Báo cáo.',
    'description': """
Realty Project — Xây dựng (rp_construction)
=============================================

Gom toàn bộ nghiệp vụ thi công về 1 menu "Xây dựng" trong Realty Project:

  Xây dựng
  ├── Dashboard Xây dựng      [rp.construction.dashboard — KPI realtime]
  ├── Lịch thi công           [rp_schedule mount]
  ├── Tiến độ                 [rp_progress mount]
  ├── Hiện trường             [rp_site mount]
  ├── RFI & Trình duyệt       [rp_rfi mount]
  └── Báo cáo                 [2 pivot khởi điểm, phát triển dần]

Dashboard theo pattern rp_dashboard/rp_finance (TransientModel +
default_get) — nhấp menu "Xây dựng" là mở dashboard.
    """,
    'author': 'BSDInsight',
    'website': 'https://bsdinsight.com',
    'license': 'AGPL-3',
    'depends': [
        'rp_schedule',
        'rp_progress',
        'rp_site',
        'rp_rfi',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/rp_construction_dashboard_views.xml',
        'views/rp_construction_report_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
