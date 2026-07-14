# -*- coding: utf-8 -*-
{
    'name': 'Realty Project — Tài chính',
    'version': '19.0.1.0.0',
    'category': 'Realty/Project',
    'summary': 'Menu Tài chính hợp nhất: Dashboard, Khái toán, Dự toán (BOQ), '
               'Tạm ứng, Hoá đơn nhà thầu, Hồ sơ thanh toán, Thanh toán, Báo cáo.',
    'description': """
Realty Project — Tài chính (rp_finance)
========================================

Gom toàn bộ dòng tiền dự án về 1 menu "Tài chính" trong Realty Project:

  Tài chính
  ├── Dashboard Tài chính     [rp.finance.dashboard — KPI realtime]
  ├── Khái toán               [rp_estimate mount]
  ├── Dự toán (BOQ)           [rp.boq.line — list + pivot]
  ├── Tạm ứng                 [rp_advance_payment mount]
  ├── Hoá đơn nhà thầu        [account.move in_invoice]
  ├── Hồ sơ thanh toán        [rp.contract.payment.milestone]
  ├── Thanh toán              [account.payment outbound]
  └── Báo cáo                 [rp_contract mount 2 báo cáo, phát triển dần]

Dashboard theo pattern rp_dashboard (TransientModel + default_get compute)
— nhấp menu "Tài chính" là mở dashboard (menu con sequence nhỏ nhất).

Chuỗi giá trị: Khái toán → Dự toán BOQ → HĐ đã ký → Nghiệm thu lũy kế
→ Tạm ứng/cấn trừ → Hoá đơn NT → Mốc thanh toán → Đã thanh toán.
    """,
    'author': 'BSDInsight',
    'website': 'https://bsdinsight.com',
    'license': 'AGPL-3',
    'depends': [
        'account',
        'rp_estimate',
        'rp_cost_base',
        'rp_contract',
        'rp_progress',
        'rp_advance_payment',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/rp_finance_dashboard_views.xml',
        'views/rp_boq_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
