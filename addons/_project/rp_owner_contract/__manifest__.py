# -*- coding: utf-8 -*-
{
    'name': 'Realty Project — HĐ với Chủ đầu tư (đầu ra)',
    'version': '19.0.1.5.0',
    'category': 'Realty/Project',
    'summary': 'HĐ thi công ĐẦU RA (tổng thầu ↔ CĐT): BBNT sản lượng với '
               'CĐT + thanh toán của CĐT → khoản phải thu (quyền đòi nợ).',
    'description': """
Realty Project — HĐ với Chủ đầu tư (rp_owner_contract)
======================================================

Chiều ĐẦU RA của tổng thầu (vd CC1): hợp đồng thi công ký với Chủ đầu
tư — đối xứng với rp_contract (HĐ ĐẦU VÀO thuê nhà thầu phụ).

Models:
- ``rp.owner.contract`` — HĐ thi công với CĐT: giá trị HĐ, trạng thái,
  tổng hợp sản lượng nghiệm thu / CĐT đã trả / **khoản phải thu**.
- ``rp.owner.acceptance`` — BBNT sản lượng ĐẦU RA (tổng thầu nghiệm thu
  VỚI CĐT). Workflow: Nháp → Đã đề xuất → CĐT duyệt / Huỷ.
- ``rp.owner.payment`` — thanh toán của CĐT (tạm ứng / theo sản lượng /
  quyết toán / khác).

Khoản phải thu = Σ BBNT approved − Σ CĐT đã trả. Có thể ÂM khi CĐT tạm
ứng trước sản lượng (bình thường trong xây dựng).

Đây là nguồn dữ liệu cho TSBĐ "Quyền đòi nợ" trong borrowing base
(module re_loan_borrowing_base): sản lượng nghiệm thu tăng → phải thu
tăng → hạn mức khả dụng tại NH tăng.
""",
    'author': 'BSDInsight',
    'website': 'https://bsdinsight.com',
    'license': 'AGPL-3',
    'depends': [
        're_base',
        'mail',
        'account',
        'rp_estimate',
        'rp_contractor',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'views/rp_owner_contract_views.xml',
        'views/rp_owner_dashboard_views.xml',
    ],
    'application': False,
    'installable': True,
}
