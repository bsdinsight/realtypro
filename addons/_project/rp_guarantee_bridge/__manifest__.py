# -*- coding: utf-8 -*-
{
    'name': 'Realty Project ↔ Bank Guarantee Bridge',
    'version': '19.0.1.2.0',
    'category': 'Realty/Project',
    'summary': 'Link HĐ nhà thầu (rp.contract) với chứng thư BL NH '
               '(re.bank.guarantee).',
    'description': """
Bridge module: HĐ nhà thầu (rp_contract) ↔ BL NH (re_guarantee).

Cung cấp:
  - Field `rp_contract_id` trên re.bank.guarantee: 1 BL phục vụ 1 HĐ NT
  - Smart button "Bảo lãnh NH" trên rp.contract: list BL của HĐ này
  - Filter / group by HĐ nhà thầu trong list BL

Cài tuỳ chọn — chỉ KH dùng cả rp_contract + re_guarantee mới cần.
    """,
    'author': 'BSDInsight',
    'website': 'https://bsdinsight.com',
    'license': 'AGPL-3',
    'depends': [
        'rp_contract',
        're_guarantee',
    ],
    'data': [
        'views/re_bank_guarantee_views.xml',
        'views/rp_contract_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
