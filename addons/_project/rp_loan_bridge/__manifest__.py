# -*- coding: utf-8 -*-
{
    'name': 'Realty Project ↔ Loan Bridge',
    'version': '19.0.1.22.0',
    'category': 'Realty/Project',
    'summary': 'Phân bổ vay/lãi vay theo công trình: Project / Khu vực / '
               'Hạng mục / Gói thầu / HĐ nhà thầu',
    'description': """
Bridge giữa re_loan (Quản lý Vay) và Realty Project.

Phân bổ Khế ước nhận nợ (KW) — gốc / lãi / cả hai — theo công trình. Hạt mịn
chọn được:

  - re.project (Dự án)
  - rp.structure (Hạng mục dự án)
  - rp.cost.category (Nhóm chi phí — vd 9.1 "Lãi vay capitalized")
  - rp.tender.package (Gói thầu)
  - rp.contract (Hợp đồng nhà thầu)

Phương pháp phân bổ: percent hoặc amount.

Use cases:
  - Capitalize lãi vay vào giá thành công trình theo VAS (TT 200, §54)
  - Theo dõi dòng tiền vay theo HĐ nhà thầu
  - Báo cáo dư nợ / chi phí lãi vay theo hạng mục

Cài tùy chọn — chỉ customer dùng cả Loan + Project mới cần.
    """,
    'author': 'BSDInsight',
    'website': 'https://bsdinsight.com',
    'license': 'AGPL-3',
    'depends': [
        're_loan',
        'account',
        'rp_cost_base',
        'rp_estimate',
        'rp_contract',
        'rp_progress',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/rp_loan_rules.xml',
        'views/rp_loan_allocation_views.xml',
        'views/re_loan_note_views.xml',
        'views/re_loan_disbursement_dossier_views.xml',
        'views/rp_structure_views.xml',
        'views/rp_contract_views.xml',
        'views/account_move_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
