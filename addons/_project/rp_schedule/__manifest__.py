# -*- coding: utf-8 -*-
{
    'name': 'Realty Project — Lịch thi công (Schedule)',
    'version': '19.0.1.1.0',
    'category': 'Realty/Project',
    'summary': 'Tầng lịch thi công theo task (Odoo Project) cho HĐ nhà '
               'thầu: import Excel/MS Project XML, WBS, %, milestone, '
               'giao việc, rollup tiến độ.',
    'description': """
Realty Project — Lịch thi công (rp_schedule)
============================================

Bổ sung tầng LỊCH THI CÔNG theo TASK (khác tầng nghiệm thu khối lượng
BBNT) — dùng engine Odoo **project** (project.task) bắc cầu sang HĐ nhà
thầu (rp.contract) + Hạng mục (rp.structure).

- project.task mở rộng: HĐ nhà thầu, Hạng mục, mã WBS, ngày KH bắt đầu/
  kết thúc, % hoàn thành, milestone, công việc trước (predecessors).
- **Import Excel / MS Project XML (MSPDI)**: nhà thầu export file → wizard
  map cột tạo task; re-import idempotent theo UID/WBS cập nhật %.
- **Rollup**: % tiến độ theo lịch của HĐ = trung bình có trọng số (số
  ngày KH) của các công việc.
- **Giao việc + workspace**: dùng assignee + "My Tasks" của Odoo Project;
  menu "Công việc của tôi" lọc theo công việc xây dựng.

Không đụng tầng nghiệm thu khối lượng (rp_progress) — 2 lăng kính song song.
""",
    'author': 'BSDInsight',
    'website': 'https://bsdinsight.com',
    'license': 'LGPL-3',
    'depends': [
        'project',
        'rp_contract',
        'rp_cost_base',
        # Gantt Syncfusion: tái dùng lib EJ2 + BSDSyncfusionGanttAdapter
        # + license param/controller của rp_progress (bản quyền BSD).
        'rp_progress',
    ],
    'data': [
        'security/ir.model.access.csv',
        'wizards/rp_schedule_import_views.xml',
        'views/project_task_views.xml',
        'views/rp_contract_views.xml',
        'views/rp_schedule_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            # Lib Syncfusion EJ2 (+ frappe fallback) do rp_progress ship —
            # KHÔNG vendor lại ở đây (tránh double-load).
            'rp_schedule/static/src/scss/rp_gantt.scss',
            'rp_schedule/static/src/js/rp_gantt.js',
            'rp_schedule/static/src/xml/rp_gantt.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
