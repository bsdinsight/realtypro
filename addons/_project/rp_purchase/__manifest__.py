# -*- coding: utf-8 -*-
{
    "name": "EPCOne — Mua sắm",
    "version": "19.0.2.1.1",
    "category": "Realty/Project",
    "summary": "Nối đơn mua vào dự án và nhóm chi phí, để chi phí chủ đầu "
               "tư tự mua có chứng từ đứng sau thay vì một dòng khai tay.",
    "description": """
Đơn mua của chủ đầu tư (rp_purchase)
====================================

Chủ đầu tư nhà máy điện **không mua vật tư** — nhà thầu mua. Trên dự án
AMI, 98,2% tiền đi qua ba hợp đồng EPC trọn gói, chỉ 1,8% là chủ đầu tư
tự mua: tư vấn giám sát độc lập (OE), bảo hiểm công trình, kiểm định,
chi phí ban quản lý dự án.

Nhưng 1,8% đó đang là **một dòng gõ tay** trong dự toán cấp dự án: không
nhà cung cấp, không chứng từ, không tiến độ chi — mà vẫn nằm trong BAC
và trong mốc ngân sách đã chốt. Module này đóng đúng lỗ đó.

Không dựng màn mua hàng mới: phân hệ Mua hàng của Odoo đã đủ. Chỉ thêm
hai trục mà nó thiếu — **dự án** và **nhóm chi phí** — rồi cộng lên dự
án thành ba lớp quen thuộc:

    dự toán (dòng chi phí cấp dự án)
      → đã cam kết (đơn mua đã xác nhận)
        → đã có hoá đơn (hoá đơn đã vào sổ)

Nhóm chi phí đặt ở DÒNG đơn mua chứ không ở đầu đơn: một đơn mua bảo
hiểm có thể gồm cả bảo hiểm công trình lẫn bảo hiểm trách nhiệm, hai
nhóm chi phí khác nhau. Đặt ở đầu đơn là ép người dùng tách đơn, và họ
sẽ không tách — họ sẽ chọn bừa một nhóm.
    """,
    "author": "BSDInsight",
    "website": "https://bsdinsight.com",
    "license": "AGPL-3",
    "depends": [
        "purchase",
        "rp_cost_base",
        "rp_estimate",
        # BẮT BUỘC: `re.project.currency_id` do rp_evm định nghĩa, và các
        # trường Monetary ở đây lấy nó làm currency_field. Thiếu khai thì
        # `-u` nổ "unknown currency_field 'currency_id'" — chỉ nổ lúc nâng
        # cấp riêng module này, còn cài lần đầu thì qua, nên rất dễ lọt.
        # View ở đây cũng kế thừa xmlid của rp_evm.
        "rp_evm",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_sequence.xml",
        "views/menu_root.xml",
        "views/rp_procure_panes.xml",
        "views/rp_purchase_request_views.xml",
        "views/purchase_order_views.xml",
        "views/rp_goods_receipt_views.xml",
        "views/rp_payment_request_views.xml",
        "views/re_project_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
