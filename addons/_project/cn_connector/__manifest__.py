# -*- coding: utf-8 -*-
{
    'name': 'Construction Network — Connector (Tổng thầu)',
    'version': '19.0.1.0.0',
    'category': 'Realty/Project',
    'summary': 'Kết nối Realty Project (tổng thầu) với BSD Construction '
               'Network: công bố gói thầu, đồng bộ hồ sơ dự thầu.',
    'description': """
Construction Network — Connector (cn_connector)
===============================================

Phía TỔNG THẦU (Odoo Realty Project) gọi API Hub:
- Cấu hình Hub URL + API key (Cấu hình → Cài đặt).
- Nút "Công bố lên Network" trên Gói thầu (rp.tender.package) → tạo gói
  thầu trên Hub.
- Nút "Đồng bộ hồ sơ dự thầu" → kéo hồ sơ dự thầu từ Hub về, tạo/cập nhật
  rp.tender.bidder.
""",
    'author': 'BSDInsight',
    'website': 'https://bsdinsight.com',
    'license': 'LGPL-3',
    'depends': ['rp_estimate'],
    'data': [
        'views/res_config_settings_views.xml',
        'views/rp_tender_package_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
