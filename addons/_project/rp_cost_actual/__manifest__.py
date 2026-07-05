# -*- coding: utf-8 -*-
{
    'name': 'Realty Project — Chi phí thực (AC)',
    'version': '19.0.1.1.0',
    'category': 'Realty/Project',
    'summary': 'Gắn chi phí thực từ hóa đơn nhà thầu vào WBS (hạng mục × '
               'nhóm chi phí) → roll-up AC cho EVM (CPI = EV/AC).',
    'description': """
Realty Project — Chi phí thực / Actual Cost (rp_cost_actual)
============================================================

Mắt xích **AC (Actual Cost)** của EVM. Trước module này, hóa đơn nhà
thầu (account.move, vendor bill) biết dự án/hợp đồng nhưng KHÔNG biết
chi cho **đầu việc/hạng mục** nào ở cấp dòng → không roll-up được chi
phí thực theo WBS để tính CPI.

Module này thêm:

- ``account.move.line.structure_id`` + ``cost_category_id`` — gắn mỗi
  dòng chi phí vào hạng mục (đầu việc) + nhóm chi phí. Hiện trên form
  hóa đơn, chỉ với vendor bill (in_invoice/in_refund).
- ``rp.structure.actual_cost`` — Σ price_subtotal các dòng hóa đơn đã
  posted gắn hạng mục (in_invoice cộng, in_refund trừ). Reactive.

Kết hợp với:
- PV/BAC = ``rp.structure.estimate_value`` (rp_progress, BOQ else Khái toán)
- EV     = ``rp.structure.progress_value`` (rp_progress, BBN nghiệm thu)
→ đủ 3 nguồn PV/EV/AC. Phase 3 (EVM engine) sẽ tính CPI/CV/EAC + cảnh
báo + dashboard trên nền này.

Approach: custom fields trên dòng hóa đơn (KHÔNG dùng analytic account
của Odoo) — nhất quán với data model rp.structure/rp.cost.category mà
Ban QLDA đã dùng. Phase 2b sẽ thêm split 1 hóa đơn → nhiều đầu việc.

Depends rp_cost_base + account (KHÔNG rp_progress → tránh phụ thuộc
vòng; AC độc lập với tiến độ).
""",
    'author': 'BSDInsight',
    'website': 'https://bsdinsight.com',
    'license': 'AGPL-3',
    'depends': [
        'rp_cost_base',
        'account',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/account_move_views.xml',
        'views/rp_structure_views.xml',
    ],
    'application': False,
    'installable': True,
}
