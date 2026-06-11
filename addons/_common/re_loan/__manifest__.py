# -*- coding: utf-8 -*-
{
    'name': 'Realty - Loan Management',
    'version': '19.0.1.51.0',
    'category': 'Realty/Finance',
    'summary': 'Quản lý vay: HĐTD, hạn mức, khế ước nhận nợ, thế chấp, '
               'vay nội bộ (foundation dùng chung cho mọi suite Realty Pro)',
    'description': """
Realty - Loan Management (re_loan)
==================================

Module foundation quản lý vay vốn cho doanh nghiệp xây dựng / tổng thầu /
chủ đầu tư. Viết MỚI 100% (clean-room), là IP của BSDInsight.

Cấu trúc nghiệp vụ:
  Hợp đồng tín dụng (HĐTD) → Hạn mức (Facility) → Khế ước nhận nợ (KW)
    → Giải ngân / Lãi / Trả nợ / Phụ lục
  + Tài sản thế chấp (multi-pledge) + Phân bổ công trình + Vay nội bộ

Xem thiết kế: docs/loan_brd.md, docs/loan_sdd.md.

**Phase L0 (skeleton)**: groups, ACL, root menu, master loại tài sản thế chấp.
Các phase sau (L1+) bổ sung credit contract, facility, note, collateral, ...
    """,
    'author': 'BSDInsight',
    'website': 'https://bsdinsight.com',
    'license': 'AGPL-3',
    'depends': [
        'base',
        'mail',
        're_party',
        're_base',
    ],
    'data': [
        'security/re_loan_groups.xml',
        'security/ir.model.access.csv',
        'security/re_loan_rules.xml',
        'data/ir_sequence_data.xml',
        'data/re_loan_vn_banks_data.xml',
        'views/menu_root.xml',
        'views/re_loan_facility_views.xml',
        'views/re_loan_credit_contract_views.xml',
        'views/re_loan_note_views.xml',
        'views/re_loan_report_views.xml',
        'views/re_loan_collateral_views.xml',
        'views/re_loan_collateral_type_views.xml',
        'data/re_loan_collateral_type_data.xml',
        'data/ir_cron_data.xml',
    ],
    'demo': [
        'demo/re_loan_demo_banks.xml',
        'demo/re_loan_demo_contracts.xml',
        'demo/re_loan_demo_notes.xml',
        'demo/re_loan_demo_collateral.xml',
        'demo/re_loan_demo_onlending.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
