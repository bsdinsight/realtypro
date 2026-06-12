# -*- coding: utf-8 -*-
{
    'name': 'Realty Project — Tender × Contract Bridge',
    'version': '19.0.1.0.0',
    'category': 'Realty/Project',
    'summary': 'Auto-tạo HĐ nhà thầu khi gói thầu chuyển sang "Đã ký HĐ"',
    'description': """
Bridge giữa rp.tender.package (Gói thầu) và rp.contract (HĐ nhà thầu).

Khi gói thầu chuyển state "Có KQ" → "Đã ký HĐ":
- System auto-tạo rp.contract draft với:
  - tender_package_id = package.id
  - contractor_id = package.contractor_id (winning partner)
  - contract_value_pretax = package.contract_amount
  - name = '{package.code}-HD' (fallback)
  - state = 'draft'
- Reverse link: package.contract_ids O2M show toàn bộ HĐ ký từ gói

User mở HĐ vừa tạo để điền VAT, % tạm ứng, lịch thanh toán, BL, etc.

Module này tách riêng để cho phép customer chỉ dùng đấu thầu (không
ký HĐ trong hệ thống) — bỏ qua cài đặt module này nếu không cần.
    """,
    'author': 'BSDInsight',
    'website': 'https://bsdinsight.com',
    'license': 'AGPL-3',
    'depends': [
        'rp_estimate',
        'rp_contract',
    ],
    'data': [
        'views/rp_tender_package_views.xml',
    ],
    'installable': True,
    'auto_install': True,
    'application': False,
}
