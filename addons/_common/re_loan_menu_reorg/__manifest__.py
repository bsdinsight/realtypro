# -*- coding: utf-8 -*-
{
    'name': 'Realty Loan — Menu Reorganization',
    'version': '19.0.1.0.0',
    'category': 'Realty/Loan',
    'summary': 'Gom 11+ top-level menu Quản lý Vay thành 7 group (HĐTD '
               '/ KW / Thanh toán / BL / Báo cáo / Cấu hình + Dashboard) '
               'để không tràn ra dấu + trên thanh menu.',
    'description': """
Pattern: override parent_id của các menuitem trong re_loan + re_guarantee
+ rp_loan_bridge bằng <record> để gom theo nhóm nghiệp vụ:

  Quản lý Vay
    ├── Dashboard
    ├── HĐ tín dụng (group)
    │     ├── Hợp đồng tín dụng
    │     ├── Hạn mức tín dụng
    │     └── Tài sản thế chấp
    ├── Khế ước (group)
    │     ├── Khế ước nhận nợ
    │     ├── Vay nội bộ
    │     └── Hóa đơn HĐ nhà thầu (nếu rp_loan_bridge installed)
    ├── Trích thu & Thanh toán (group)
    │     ├── Trích thu tự động (NH)
    │     └── Import giấy báo nợ
    ├── Bảo lãnh NH (parent có sẵn từ re_guarantee)
    ├── Báo cáo (parent có sẵn)
    └── Cấu hình (parent có sẵn)
""",
    'author': 'BSD Insight',
    'website': 'https://bsdinsight.com',
    'license': 'LGPL-3',
    'depends': [
        're_loan',
        're_guarantee',
        're_loan_dashboard',
        # rp_loan_bridge: SOFT dep — không đưa vào hard depends để
        # `auto_install=True` trigger ngay khi đủ 3 module trên (kể cả
        # tenant chưa install rp_loan_bridge). Hook `_reorg_menus`
        # defensive search xmlid `rp_loan_bridge.menu_*` qua
        # env.ref(raise_if_not_found=False) — skip nếu không có.
    ],
    'data': [
        'views/menu_reorg.xml',
    ],
    'post_init_hook': '_reorg_menus',
    'installable': True,
    'auto_install': True,  # tự install khi đủ depends — admin không
                           # cần thao tác tay
}
