# -*- coding: utf-8 -*-
{
    'name': 'Realty Project - Advance ↔ Guarantee Bridge',
    'version': '19.0.1.0.0',
    'category': 'Realty/Project',
    'summary': 'Giải ngân tạm ứng → chọn bảo lãnh nhận từ nhà thầu '
               '(BL tạm ứng) của nhà thầu đó, kiểm tra bao phủ.',
    'description': """
Bridge: Tạm ứng (rp_advance_payment) ↔ Bảo lãnh nhận từ nhà thầu
(rp_contract_guarantee).

Khi Hồ sơ giải ngân chọn Tạm ứng → hiện thêm ô chọn **Bảo lãnh nhận từ
nhà thầu** (thường là BL tạm ứng / hoàn tạm ứng), lọc theo đúng nhà thầu
của tạm ứng đó; hiển thị giá trị + hạn bảo lãnh và cảnh báo nếu bảo lãnh
không đủ bao phủ số tiền tạm ứng.

Cài tự động khi có cả 2 module.
    """,
    'author': 'BSDInsight',
    'website': 'https://bsdinsight.com',
    'license': 'AGPL-3',
    'depends': [
        'rp_advance_payment',
        'rp_contract_guarantee',
    ],
    'data': [
        'views/rp_loan_disbursement_dossier_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': True,
}
