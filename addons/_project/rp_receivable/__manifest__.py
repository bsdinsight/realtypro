# -*- coding: utf-8 -*-
{
    "name": "EPCOne — Công nợ phải thu & phải trả",
    "version": "19.0.1.0.1",
    "category": "Realty/Project",
    "summary": "Hoá đơn bán ra, thu tiền, và tuổi nợ cả hai chiều phải thu / phải trả.",
    "description": """
EPCOne — Công nợ phải thu (rp_receivable)
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
        # account_payment TRƯỚC account_move_payable: tệp payable tham
        # chiếu view_rp_ar_payment_list khai trong tệp payment. Đảo thứ
        # tự là cài mới chết với "External ID not found" — bản đã cài
        # thì không thấy, nên lỗi chỉ lộ ra ở khách MỚI.
        "views/account_payment_views.xml",
        "views/account_move_payable_views.xml",
        "views/menu.xml",
    ],
    "installable": True,
    "application": False,
}
