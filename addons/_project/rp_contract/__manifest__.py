# -*- coding: utf-8 -*-
{
    'name': 'Realty Project - Contractor Contracts',
    'version': '19.0.1.4.0',
    'category': 'Realty/Project',
    'summary': 'Hợp đồng nhà thầu (rp.contract): lifecycle, BOQ lines, '
               'lịch thanh toán, phụ lục, bảo lãnh',
    'description': """
Realty Project - Hợp đồng nhà thầu (rp.contract)
================================================

Quản lý hợp đồng giữa Chủ đầu tư / Tổng thầu và Nhà thầu (sau khi đấu thầu).

Chuỗi đầy đủ: Project → Khu vực → Hạng mục → Gói thầu → **Hợp đồng nhà thầu**.

Phạm vi v1:
  - rp.contract entity với lifecycle draft→signed→executing→completed,
    nhánh terminated
  - Khối lượng BOQ (rp.contract.line) — optional
  - Lịch thanh toán milestone (rp.contract.payment.milestone)
  - Phụ lục HĐ (rp.contract.amendment) — 6 loại
  - Bảo lãnh thực hiện / tạm ứng / bảo hành — text fields (sẽ FK
    khi rf_bank_guarantee ship sau)
  - Báo cáo: pivot HĐ theo dự án / nhà thầu / trạng thái, tiến độ thanh toán
  - Inherit rp.tender.package thêm smart button HĐ

NGOÀI scope v1 (làm sau):
  - Multi-bidder + award workflow trên gói thầu
  - Tích hợp account.move (xuất hoá đơn, bút toán)
  - Liên kết với rf_bank_guarantee (chưa ship)
  - Phân bổ vay theo HĐ (sẽ làm ở rp_loan_bridge L5)
    """,
    'author': 'BSDInsight',
    'website': 'https://bsdinsight.com',
    'license': 'AGPL-3',
    'depends': [
        'base',
        'mail',
        're_base',
        'rp_contractor',
        'rp_cost_base',
        'rp_estimate',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/rp_contract_views.xml',
        'views/rp_tender_package_views.xml',
        'views/rp_contract_report_views.xml',
        'views/menu.xml',
    ],
    'demo': [
        'demo/rp_contract_demo.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
