# -*- coding: utf-8 -*-
{
    'name': 'Realty Project — Hồ sơ dự thầu (nhà thầu)',
    'version': '19.0.15.0.0',
    'category': 'Realty/Project',
    'summary': 'Nhà thầu nhận gói thầu, chia hạng mục của mình và dựng '
               'BoQ để tính ra giá dự thầu.',
    'description': """
Hồ sơ dự thầu — phía NHÀ THẦU
=============================

Realty Project vốn mô tả chiều **mời thầu**: chủ đầu tư / tổng thầu chia
dự án thành hạng mục, ra BoQ, lập gói thầu rồi chấm nhà thầu. Module này
bổ sung chiều còn lại — **đi dự thầu**::

    Dự án
     └─ Hạng mục dự án ─ BoQ dự án            ← chủ đầu tư / tổng thầu
     └─ Gói thầu
          └─ Hồ sơ dự thầu                    ← module này
               └─ Hạng mục nhà thầu           ← cấp thấp hơn hạng mục dự án
                    └─ BoQ nhà thầu           ← cấp thấp hơn BoQ dự án
                         └─ Bóc tách khối lượng

Bốn thứ mà BoQ dự án không làm được, nên phải có bảng riêng:

* **Ba đơn giá** vật liệu / nhân công / máy thay vì một ô đơn giá gộp;
* **Cờ ai cấp vật tư** — phần bên mời thầu tự cấp vẫn bóc để biết tổng
  giá trị nhưng KHÔNG cộng vào giá chào;
* **Bóc tách khối lượng** có diễn giải, cho phép dòng trừ mang dấu âm;
* **Markup 5 tầng** theo dự toán Việt Nam (chi phí chung, nhà tạm, công
  việc không xác định khối lượng, TNCTT, VAT) — đặt ở hồ sơ vì đây là
  quyết định thương mại của từng gói, không phải hằng số kỹ thuật.

Hạng mục và BoQ của nhà thầu để BẢNG RIÊNG, không phải cấp thứ ba của
``rp.structure``: bảng đó nuôi ``estimate_value`` → BAC của EVM, trộn
vào sẽ làm ngân sách dự án bị đếm hai lần.
""",
    'author': 'BSDInsight',
    'website': 'https://bsdinsight.com',
    'license': 'AGPL-3',
    'depends': [
        're_base',
        'rp_cost_base',
        'rp_progress',
        'rp_estimate',
        # Master tài nguyên + cây nhóm (rp.resource, rp.resource.category)
        # sống ở đây. Không dựng master riêng để tránh hai nguồn dữ liệu
        # cho cùng một cần cẩu 25 tấn.
        'rp_cost_library',
    ],
    'data': [
        'security/ir.model.access.csv',
        # Menu gốc + ba nhóm phải có TRƯỚC mọi file view gắn menu con.
        'views/rp_bid_menu_root.xml',
        'views/rp_bid_project_views.xml',
        'views/rp_bid_item_views.xml',
        'views/rp_bid_views.xml',
        'views/rp_bid_structure_views.xml',
        'views/rp_bid_takeoff_views.xml',
        'views/rp_bid_element_views.xml',
        'views/rp_bid_resource_views.xml',
        'views/rp_bid_price_views.xml',
        'views/rp_bid_menu.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
