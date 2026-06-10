# -*- coding: utf-8 -*-
{
    'name': 'Realty Loan ↔ Accounting',
    'version': '19.0.1.4.0',
    'category': 'Realty/Finance',
    'summary': 'Tích hợp kế toán cho re_loan: post bút toán giải ngân / lãi / '
               'trả nợ; capitalize lãi vay theo công trình.',
    'description': """
Module tích hợp re_loan với Odoo Accounting (account.move).

Configurable account mapping (KHÔNG hardcode COA):
  - Tài khoản Vay (TK 3411/3412)
  - Tài khoản Tiền gửi NH (TK 1121)
  - Tài khoản Lãi vay phải trả (TK 33531)
  - Tài khoản CP lãi vay (TK 635 — khi không capitalize)
  - Tài khoản XDCB dở dang (TK 241 — khi capitalize)

Per-company defaults (Settings) + per-facility override.

Bút toán tạo MANUAL qua nút "Post" trên giải ngân / dòng lịch lãi / trả nợ
(kế toán review trước khi post — quy ước VN).

Capitalization lãi vay:
  - Nếu rp_loan_bridge cài + KW có allocation tới cost category capitalize
    → một phần lãi tự động vào TK 241 (XDCB) theo % allocation
  - Phần còn lại → TK 635 (CP lãi)
  - Nếu bridge không cài → toàn bộ vào TK 635

KHÔNG depend l10n_vn. Customer dùng COA nào cũng map được.
    """,
    'author': 'BSDInsight',
    'website': 'https://bsdinsight.com',
    'license': 'AGPL-3',
    'depends': [
        're_loan',
        'account',
    ],
    'data': [
        'views/res_config_settings_views.xml',
        'views/re_loan_facility_views.xml',
        'views/re_loan_note_views.xml',
        'views/report_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
