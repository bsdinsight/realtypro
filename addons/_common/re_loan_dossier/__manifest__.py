# -*- coding: utf-8 -*-
{
    'name': 'Realty — Hồ sơ giải ngân',
    'version': '19.0.1.0.0',
    'category': 'Realty/Finance',
    'summary': 'Hồ sơ giải ngân theo hoá đơn: mỗi lần giải ngân gồm '
               'nhiều hồ sơ, mỗi hồ sơ một hoá đơn nhà thầu.',
    'description': """
Realty — Hồ sơ giải ngân (re_loan_dossier)
==========================================

Ngân hàng không giải ngân theo một con số tổng: mỗi lần giải ngân phải
kèm hồ sơ chứng minh tiền đi đâu — hoá đơn của nhà thầu, kèm chứng từ
scan. Module này là phần LÕI của việc đó:

  - mỗi giải ngân có nhiều hồ sơ, mỗi hồ sơ gắn 1 hoá đơn mua vào;
  - một hoá đơn chia được cho nhiều lần giải ngân, và hệ thống chặn
    phân bổ quá số còn lại của hoá đơn;
  - Σ giá trị hồ sơ phải khớp số tiền giải ngân trước khi gửi NH.

Chỉ phụ thuộc phân hệ vay + kế toán, KHÔNG phụ thuộc bộ Thi công của
Realty. Chỗ nối biên bản nghiệm thu và hợp đồng nhà thầu để mở: khách
dùng bộ Thi công của Realty thì cài `rp_loan_bridge`; khách có hệ hợp
đồng / nghiệm thu riêng thì viết một module nhỏ kế thừa
`rp.loan.disbursement.dossier` và thêm liên kết của mình.
    """,
    'author': 'BSDInsight',
    'website': 'https://bsdinsight.com',
    'license': 'AGPL-3',
    'depends': [
        're_loan',
        'account',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/re_loan_disbursement_dossier_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
