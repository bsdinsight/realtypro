# -*- coding: utf-8 -*-
{
    "name": "Realty Project — Công nợ phải thu",
    "version": "19.0.1.0.0",
    "category": "Realty/Project",
    "summary": "Hoá đơn bán ra, thu tiền và tuổi nợ phải thu cho dự án.",
    "description": """
Realty Project — Công nợ phải thu (rp_receivable)
=================================================

Gom ba màn vào nhánh Tài chính: hoá đơn bán ra, thu tiền, và công nợ
phải thu chia theo TUỔI NỢ.

Tuổi nợ là trường LƯU, không phải tính lúc đọc — để còn gom nhóm và lọc
được trên danh sách. Đổi lại nó cũ đi mỗi ngày, nên có cron chạy 01:00
tính lại. Hoá đơn vừa ghi sổ hay vừa thu tiền thì tính lại ngay, không
chờ cron.
""",
    "author": "BSD Insight",
    "license": "LGPL-3",
    "depends": ["account", "rp_estimate"],
    "data": [
        "data/ir_cron.xml",
        "views/account_move_views.xml",
        "views/account_payment_views.xml",
        "views/menu.xml",
    ],
    "installable": True,
    "application": False,
}
