# -*- coding: utf-8 -*-
{
    'name': 'BSD Construction Network — Hub',
    'version': '19.0.1.0.0',
    'category': 'Construction Network',
    'summary': 'Mạng lưới nhà thầu & NCC vật liệu: hồ sơ nhà thầu, bảng '
               'gói thầu, dự thầu, portal cộng tác. Kết nối nhiều tổng thầu.',
    'description': """
BSD Construction Network — Hub (cn_hub)
=======================================

Nền tảng mạng lưới B2B ngành xây dựng (backend Odoo). MVP: **Hub nhà thầu**.

- **Hồ sơ nhà thầu** (res.partner mở rộng): chuyên môn, giấy phép, khu vực,
  đánh giá, xác minh. 1 hồ sơ → kết nối nhiều tổng thầu.
- **Bảng gói thầu** (cn.tender): tổng thầu công bố gói thầu lên Network.
- **Dự thầu** (cn.bid): nhà thầu nộp hồ sơ + giá.
- **Portal**: nhà thầu đăng nhập xem gói thầu mở + nộp dự thầu + theo dõi.
- **API**: nhận gói thầu từ Odoo tổng thầu + trả hồ sơ dự thầu (connector).

Phase sau: market vật liệu (catalog/RFQ), cộng tác dự án (tiến độ/nghiệm
thu/nhật ký công trường), đánh giá/review, Next.js frontend.
""",
    'author': 'BSDInsight',
    'website': 'https://bsdinsight.com',
    'license': 'LGPL-3',
    'depends': ['base', 'mail', 'portal'],
    'data': [
        'security/ir.model.access.csv',
        'security/cn_hub_security.xml',
        'views/cn_tender_views.xml',
        'views/res_partner_views.xml',
        'views/cn_hub_menus.xml',
        'views/cn_portal_templates.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
