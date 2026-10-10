# -*- coding: utf-8 -*-
{
    'name': 'EAMOne — Lưới cây sổ tài sản',
    'version': '19.0.1.0.0',
    'category': 'EAMOne',
    'summary': 'Vừa thấy cây vừa thấy cột: lọc, sắp xếp, xuất Excel ngay '
               'trên lưới.',
    'description': """
Lưới cây sổ tài sản
===================

Kiểu xem ``hierarchy`` sẵn có của Odoo vẽ **thẻ kiểu sơ đồ tổ chức** —
thấy hình cây nhưng **không có cột**. Sổ tài sản thì thứ người ta cần là
*vừa thấy cây vừa thấy số liệu*: sê-ri, loại cấu phần, bảo hành còn mấy
ngày, mức trọng yếu — bung ra thu vào ngay trên lưới, lọc và sắp xếp
theo từng cột, xuất Excel.

Hai kiểu xem **bổ cho nhau, không thay nhau**: thẻ để nhìn hình dáng,
lưới để làm việc với số. Nên ``hierarchy`` vẫn giữ nguyên.

Ba quyết định
-------------

**① Dữ liệu dạng PHẲNG có trỏ cha**, không phải lồng nhau. Odoo đọc ra
đã sẵn phẳng, không phải dựng cây trong Python rồi lại rã ra trong
JavaScript; và lọc, tìm kiếm trên lưới chạy thẳng trên mảng phẳng, dạng
lồng nhau phải duyệt đệ quy mỗi lần gõ phím.

**② Khoá là ``id`` SỐ của Odoo, không phải mã tài sản.** EJ2 **mất sạch
dòng mà khung vẫn vẽ** nếu khoá chứa dấu cách — nhìn như lỗi dữ liệu,
thực ra là lỗi khoá, và đã dính một lần ở Gantt. Mã tài sản hôm nay
không có dấu cách, nhưng không có gì bảo đảm khách hàng sau cũng vậy.

**③ Lọc theo nhánh CHA.** Gõ "hộp số" thì giữ luôn cây dẫn xuống nó, chứ
không bày ra một đống dòng mồ côi không biết thuộc máy nào.

Thư viện nạp **theo yêu cầu** qua ``bsd_syncfusion`` — mở màn này mới
tải, không nằm trong bundle nền.
""",
    'author': 'BSD Insight',
    'website': 'https://bsdinsight.com',
    'license': 'AGPL-3',
    'depends': ['eam_core', 'bsd_syncfusion'],
    'data': ['views/eam_tree_views.xml'],
    'assets': {
        'web.assets_backend': [
            'eam_tree/static/src/scss/eam_asset_tree.scss',
            'eam_tree/static/src/js/eam_asset_tree.js',
            'eam_tree/static/src/xml/eam_asset_tree.xml',
        ],
    },
    'installable': True,
}
