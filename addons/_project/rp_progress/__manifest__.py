# -*- coding: utf-8 -*-
{
    'name': 'Realty Project — Quản lý Tiến độ',
    'version': '19.0.1.24.4',
    'category': 'Realty/Project',
    'summary': 'Quản lý tiến độ thi công: BBN Nghiệm thu Khối lượng (BBN KLCV) '
               'theo HĐ nhà thầu, rolled-up tiến độ theo hạng mục/dự án.',
    'description': """
Realty Project — Quản lý Tiến độ (rp_progress)
================================================

Module quản lý tiến độ thi công cho tổng thầu / chủ đầu tư VN. Xương sống
là **Biên bản Nghiệm thu Khối lượng (BBN KLCV)** — chứng từ pháp lý xác
nhận khối lượng đã thi công của 1 HĐ nhà thầu trong 1 kỳ.

**Phase P1 (module này) — BBN core + rolled-up progress:**

  - re.project           ← weighted_progress_percent (rolled-up từ structure)
       └── rp.structure  ← progress_percent (rolled-up từ acceptance line)
            └── rp.contract  ← acceptance_value_to_date, progress_percent
                 └── rp.progress.acceptance (BBN KLCV) [entity LÕI]
                      └── rp.progress.acceptance.line (BOQ × KL)

Workflow BBN: Nháp → Đã đề xuất → CĐT duyệt → (auto) Payment milestone
SLA: HĐ có thể quy định N ngày để CĐT trả lời, hệ thống cảnh báo nếu trễ.

Phase tiếp theo (P2-P4) sẽ bổ sung:
  - P2: Loan integration — BBN approved → unlock disbursement tranche
  - P3: Gantt chart + 2 báo cáo PDF
  - P4: EVM (PV/EV/AC/SPI/CPI) + dashboard + cảnh báo delay
    """,
    'author': 'BSDInsight',
    'website': 'https://bsdinsight.com',
    'license': 'AGPL-3',
    'depends': [
        're_base',
        're_core',   # mount menu ĐVT (Xây dựng) vào Realty Core > Configuration
        'account',
        'rp_cost_base',
        'rp_contractor',
        'rp_estimate',
        'rp_contract',
    ],
    'data': [
        'security/rp_progress_groups.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'data/rp_progress_uom_data.xml',
        'data/syncfusion_license_param.xml',
        'views/rp_progress_uom_views.xml',
        'views/rp_progress_acceptance_views.xml',
        'views/rp_structure_views.xml',
        'views/rp_contract_views.xml',
        'views/rp_contract_milestone_views.xml',
        'views/rp_milestone_acceptance_views.xml',
        'views/re_project_views.xml',
        'views/menu.xml',
    ],
    'assets': {
        'web.assets_backend': [
            ('include', 'web._assets_helpers'),
            # Syncfusion EJ2 v33.1.44 — load order strict:
            #   1. material.css — theme
            #   2. ej2.min.js — base + tất cả deps (29 MB, lớn nhưng cần)
            #   3. ej2-gantt.min.js — Gantt component, expect ej.base ready
            'rp_progress/static/lib/syncfusion/material.css',
            'rp_progress/static/lib/syncfusion/ej2.min.js',
            'rp_progress/static/lib/syncfusion/ej2-gantt.min.js',
            # Frappe-Gantt giữ lại làm fallback nếu Syncfusion fail
            # (KHÔNG auto fallback — yêu cầu admin retry, theo quyết định của khách hàng)
            'rp_progress/static/lib/frappe-gantt/frappe-gantt.css',
            'rp_progress/static/lib/frappe-gantt/frappe-gantt.js',
            'rp_progress/static/src/scss/bsd_gantt.scss',
            'rp_progress/static/src/js/bsd_gantt/bsd_gantt_adapter.js',
            'rp_progress/static/src/js/bsd_gantt/bsd_frappe_gantt_adapter.js',
            'rp_progress/static/src/js/bsd_gantt/bsd_syncfusion_gantt_adapter.js',
            'rp_progress/static/src/js/bsd_gantt/bsd_gantt_view.js',
            'rp_progress/static/src/js/bsd_gantt/bsd_gantt_view.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
