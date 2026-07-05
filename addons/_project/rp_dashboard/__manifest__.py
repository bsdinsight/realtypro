# -*- coding: utf-8 -*-
{
    'name': 'Realty Project — Dashboard',
    'version': '19.0.1.0.0',
    'category': 'Realty/Dashboard',
    'summary': 'Trang chủ KPI cho Realty Project — số liệu Dự án + HĐ '
               'thầu + Tạm ứng + Vay + Bảo lãnh + Cảnh báo, mở mặc định '
               'khi user login.',
    'description': """
Realty Project — Dashboard (rp_dashboard)
==========================================

TransientModel singleton-ish `rp.project.dashboard` tổng hợp KPI
nghiệp vụ Realty Project. Mỗi khi user open menu Dashboard, hệ thống
tạo 1 record mới với default_get() compute current KPIs.

KPI groups:
  1. Dự án      — số active, tiến độ TB, tổng vốn đầu tư
  2. HĐ thầu    — số đang thi công, tổng giá trị, đã thanh toán
  3. Tạm ứng    — chờ duyệt, đã giải ngân, chưa hoàn ứng
  4. Vay HĐTD   — tổng dư nợ gốc, lãi đã trả, KW sắp đáo hạn
  5. Bảo lãnh   — BL outstanding, BL sắp hết hạn
  6. Cảnh báo   — KW quá hạn, BL hết hạn chưa gia hạn

Click smart-button → drill-down list view filter sẵn.

Home action: hook `res.users.action_id` = dashboard cho mọi user mới.
Admin có thể đổi qua Settings → Users → Home Action.
""",
    'author': 'BSD Insight',
    'website': 'https://bsdinsight.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        're_base',
        're_loan',
        're_guarantee',
        'rp_contract',
        # rp_advance_payment: SOFT depend — dashboard check qua
        # env['rp.advance.payment'].search... try/except. Module này
        # đang có XML parse bug trên Odoo 19 (rp_advance_groups.xml),
        # hard-depend sẽ block install dashboard.
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/rp_project_dashboard_views.xml',
        'views/rp_dashboard_menu.xml',
    ],
    'post_init_hook': '_post_init_set_home_action',
    'installable': True,
    'application': True,
    'auto_install': False,
}
