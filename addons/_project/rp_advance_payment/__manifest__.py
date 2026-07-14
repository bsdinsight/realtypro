# -*- coding: utf-8 -*-
{
    'name': 'Realty Project — Tạm ứng (Advance Payment)',
    'version': '19.0.1.2.0',
    'category': 'Realty/Finance',
    'summary': 'Quản lý Tạm ứng cho HĐ nhà thầu / NCC với workflow '
               'phê duyệt + giải ngân bằng KW + cấn trừ thủ công vào hóa đơn',
    'description': """
Realty Project — Tạm ứng (rp_advance_payment)
==============================================

Quy trình nghiệp vụ:

1. **Tạo Tạm ứng** cho HĐ nhà thầu (rp.contract) hoặc PO mua hàng
   (purchase.order). KTT điền giá trị + mục đích.
2. **Phê duyệt** 1 cấp: Manager xét duyệt.
3. **Thanh toán Tạm ứng bằng KW**: tạo KW vay NH → giải ngân →
   Hồ sơ giải ngân pick Tạm ứng (thay vì invoice). KW activate
   → Tạm ứng chuyển 'Đã thanh toán'.
4. **Nhận Hóa đơn** từ nhà thầu/NCC: tạo vendor bill bình thường.
5. **Cấn trừ thủ công**: KTT mở Tạm ứng → tab "Cấn trừ" → thêm
   dòng cấn trừ vào invoice (1 Tạm ứng → nhiều Hóa đơn).
6. Khi cấn trừ đủ → Tạm ứng 'Đã cấn trừ đủ'.

State machine:
  draft → to_approve → approved → paid → settled
                                       └→ cancelled (any state trừ settled)

Models:
  - rp.advance.payment: header tạm ứng
  - rp.advance.settlement: dòng cấn trừ tạm ứng vào invoice
    """,
    'author': 'BSDInsight',
    'website': 'https://bsdinsight.com',
    'license': 'AGPL-3',
    'depends': [
        're_base',
        'account',
        'purchase',
        'rp_contract',
        'rp_loan_bridge',
    ],
    'data': [
        'security/rp_advance_groups.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'views/rp_advance_payment_views.xml',
        'views/rp_contract_inherit_views.xml',
        'views/purchase_order_inherit_views.xml',
        'views/account_move_inherit_views.xml',
        'views/re_loan_disbursement_dossier_inherit_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
