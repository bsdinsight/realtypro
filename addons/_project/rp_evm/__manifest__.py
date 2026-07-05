# -*- coding: utf-8 -*-
{
    'name': 'Realty Project — EVM (Kiểm soát chi phí)',
    'version': '19.0.1.2.0',
    'category': 'Realty/Project',
    'summary': 'Earned Value Management: CPI/CV/EAC/VAC + cảnh báo vượt chi '
               'theo hạng mục, rollup dự án.',
    'description': """
Realty Project — EVM engine (rp_evm)
====================================

Tính các chỉ số Earned Value Management từ 3 nguồn đã có trên
``rp.structure``:

- PV / BAC = ``estimate_value`` (rp_progress — BOQ else Khái toán)
- EV       = ``progress_value`` (rp_progress — BBN nghiệm thu)
- AC       = ``actual_cost``    (rp_cost_actual — hóa đơn nhà thầu)

Chỉ số **kiểm soát chi phí** (Phase 3a):

- CV  = EV − AC                (Cost Variance; âm = vượt chi)
- CPI = EV / AC                (Cost Performance Index; <1 = vượt chi)
- EAC = BAC / CPI              (Estimate At Completion; dự báo chi cuối)
- ETC = EAC − AC              (Estimate To Complete)
- VAC = BAC − EAC             (Variance At Completion; âm = vượt ngân sách)
- cost_status: no_data / on_budget (CPI≥1) / watch (0.90≤CPI<1) /
  over (CPI<0.90) + cost_alert cho lọc nhanh.

Rollup ``re.project``: total BAC/EV/AC, project CPI/EAC/VAC, số hạng
mục vượt chi.

SPI/SV (schedule performance) cần PV time-phased → Phase 4. Dashboard
Ban QLDA → Phase 3b.
""",
    'author': 'BSDInsight',
    'website': 'https://bsdinsight.com',
    'license': 'AGPL-3',
    'depends': [
        'rp_progress',
        'rp_cost_actual',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/rp_structure_views.xml',
        'views/re_project_views.xml',
        'views/rp_evm_dashboard_views.xml',
    ],
    'application': False,
    'installable': True,
}
