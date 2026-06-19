# -*- coding: utf-8 -*-
{
    'name': 'Realty — Bank Guarantee Management',
    'version': '19.0.1.14.0',
    'category': 'Realty/Finance',
    'summary': 'Quản lý chứng thư bảo lãnh ngân hàng: dự thầu, thực hiện HĐ, '
               'tạm ứng, bảo hành, thanh toán — phí + ký quỹ + lifecycle.',
    'description': """
Realty — Bank Guarantee Management (re_guarantee)
==================================================

Module quản lý chi tiết chứng thư bảo lãnh ngân hàng (LG / BG).

Tính năng:
  - Entity re.bank.guarantee với 6 loại BL phổ biến VN:
    + Bảo lãnh dự thầu (bid bond)
    + Bảo lãnh thực hiện HĐ (performance bond)
    + Bảo lãnh tạm ứng (advance payment guarantee)
    + Bảo lãnh bảo hành (warranty bond)
    + Bảo lãnh thanh toán (payment guarantee)
    + Khác

  - Tracking đầy đủ:
    + Số chứng thư, ngày phát hành, ngày hết hạn
    + Bên xin BL (applicant) — vd CC1
    + Bên thụ hưởng (beneficiary) — vd CĐT
    + NH phát hành, chi nhánh
    + Giá trị BL, phí BL (% năm + số tiền)
    + Ký quỹ (% + số tiền)
    + Đính kèm file PDF chứng thư

  - Lifecycle:
    Nháp → Đã phát hành → (Đã gia hạn) → Đã giải tỏa / Hết hạn / Bị thu

  - Phụ lục chứng thư (gia hạn / đổi giá trị / huỷ)

  - Cron tự cảnh báo BL sắp hết hạn (30 ngày) và tự đặt expired

  - Integration:
    + Link với re.loan.facility (loại guarantee_line) — BL chiếm hạn mức
    + Link với rp.contract (HĐ thầu) — BL phục vụ HĐ nào

Tuỳ chọn cài — chỉ KH cần quản lý chi tiết chứng thư BL mới cài.
    """,
    'author': 'BSDInsight',
    'website': 'https://bsdinsight.com',
    'license': 'AGPL-3',
    'depends': [
        'base',
        'mail',
        're_party',
        're_loan',
    ],
    'data': [
        'security/re_guarantee_groups.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'data/ir_cron_data.xml',
        'views/re_bank_guarantee_views.xml',
        'views/re_loan_facility_views.xml',
        'views/re_loan_credit_contract_views.xml',
        'views/re_guarantee_request_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
