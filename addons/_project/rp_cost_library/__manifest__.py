# -*- coding: utf-8 -*-
{
    'name': 'RealtyPro — Thư viện đơn giá (Cost Library)',
    'version': '19.0.0.1.0',
    'category': 'RealtyPro/Cost',
    'summary': 'Master tiêu chuẩn kỹ thuật (TCVN/QCVN/TCCS/nước ngoài) có '
               'phiên bản + thay thế. Nền cho thư viện đơn giá theo định '
               'mức nhà nước.',
    'description': """
RealtyPro — Thư viện đơn giá
============================

Bản đặc tả: docs/design/vn_cost_data_pattern.md

Bước 1 (module này): **Master tiêu chuẩn**. Độc lập, không đụng dữ liệu cũ.

- `rp.standard` — TCVN 6260 · QCVN 16 · ASTM C91. Có `country_id` (VN/US/…),
  phân loại tiêu chuẩn/quy chuẩn/cơ sở, `is_mandatory` (QCVN = bắt buộc).
- `rp.standard.edition` — TCVN 6260:**2020** vs :**2009**, có `superseded_by_id`.

Giá trị ngay: bắt được ca "nhà cung cấp chào theo bản tiêu chuẩn đã bị thay"
(vd Vicem Bút Sơn khai PCB30 theo TCVN 6260:2009 — bản đã bị 2020 thay).
""",
    'author': 'BSDInsight',
    'website': 'https://realtypro.vn',
    'license': 'LGPL-3',
    'depends': ['base', 'uom', 'product', 're_core', 'rp_progress'],
    'data': [
        'security/ir.model.access.csv',
        'views/rp_standard_views.xml',
        'views/rp_resource_views.xml',
        'views/rp_norm_views.xml',
        'views/rp_price_views.xml',
        'views/rp_unit_price_views.xml',
        'wizards/rp_gxd_import_views.xml',
        'views/rp_boq_bridge_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
