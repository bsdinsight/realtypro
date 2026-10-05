# -*- coding: utf-8 -*-
{
    "name": "Realty Project — Chi phí ↔ Tài khoản kế toán",
    "version": "19.0.1.0.0",
    "category": "Realty/Project",
    "summary": "Gắn tài khoản kế toán (TT200) vào danh mục chi phí, "
               "để đẩy số sang phần mềm kế toán (Bravo / SAP / Oracle).",
    "description": """
Chi phí ↔ Tài khoản kế toán (rp_cost_account)
=============================================

Danh mục chi phí của Realty Project chia theo cách NGƯỜI LÀM DỰ ÁN nghĩ
(đất, tư vấn, kết cấu, cơ điện, thiết bị…). Phần mềm kế toán lại chia
theo hệ thống tài khoản. Module này nối hai cách chia đó: mỗi mã chi phí
mang một tài khoản kế toán, nên mọi chứng từ gắn mã chi phí đều biết
phải vào tài khoản nào khi đẩy sang Bravo / SAP / Oracle.

Vì sao tách thành module riêng: danh mục chi phí (`rp_cost_base`) phải
chạy được ở bản triển khai KHÔNG cài phân hệ kế toán. Nhét thẳng trường
`account.account` vào đó là ép cả sản phẩm phải kéo theo phân hệ kế toán
của Odoo.

Có sẵn nút **"Gán tài khoản theo TT200"**: lấp sẵn tài khoản cho bộ danh
mục chuẩn 10 nhóm theo cách hạch toán của CHỦ ĐẦU TƯ — chi phí đầu tư
vốn hoá vào 2412 (Xây dựng cơ bản) / 2411 (Mua sắm TSCĐ). Nhà thầu hạch
toán khác (154 / 621 / 622 / 623 / 627) nên nút này KHÔNG dùng được cho
vai nhà thầu; sửa tay hoặc viết bộ gán riêng.
    """,
    "author": "BSDInsight",
    "website": "https://bsdinsight.com",
    "license": "AGPL-3",
    "depends": [
        "rp_cost_base",
        "rp_estimate",
        "account",
    ],
    "data": [
        "views/rp_cost_category_views.xml",
        "views/menus.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
