# -*- coding: utf-8 -*-
{
    'name': 'Realty Project — Hoá đơn phải gắn dự án',
    'version': '19.0.1.0.0',
    'category': 'Realty/Project',
    'summary': 'Cảnh báo mềm khi hoá đơn mua vào / bán ra chưa gắn dự án '
               '— hoá đơn trống ngữ cảnh rơi khỏi Công nợ NCC và AC của '
               'EVM, làm nhu cầu vốn và biên lợi nhuận tính lệch.',
    'description': """
Vì sao cần
==========

App Hoá đơn (Invoicing) của Odoo là một cửa nhập KHÔNG mang ngữ cảnh dự
án. Hoá đơn tạo thẳng ở đó không có `project_id` (chỉ tự suy ra từ mốc
thanh toán HĐ nhà thầu) và không có `owner_project_id` (chỉ có khi gắn
HĐ với CĐT). Hoá đơn như vậy biến mất khỏi ④ Công nợ NCC của phiếu Nhu
cầu vốn và khỏi chi phí đã thực hiện (AC) của EVM.

Vì tồn tại hai cửa cho cùng một việc — app Hoá đơn trần, và Công nợ nhà
thầu / Doanh thu CĐT có sẵn hợp đồng — người dùng sẽ chọn cửa gần nhất,
thường là cửa không có ngữ cảnh.

Module này KHÔNG chặn ghi sổ: hoá đơn ngoài dự án là có thật (thuê văn
phòng, lương khối gián tiếp, phí ngân hàng), chặn cứng sẽ buộc kế toán
gắn bừa một dự án — sai còn tệ hơn để trống. Thay vào đó:

- cờ **"Không thuộc dự án nào"** để khai có chủ đích;
- **băng đỏ** trên phiếu khi chưa gắn mà cũng chưa khai;
- **bộ lọc "Chưa gắn dự án"** + cột Dự án trên danh sách hoá đơn;
- ghi sổ vẫn chạy, nhưng để lại ghi chú trong chatter để còn truy.
""",
    'author': 'BSD Insight',
    'website': 'https://bsdinsight.com',
    'license': 'LGPL-3',
    'depends': [
        # project_id (hoá đơn nhà thầu) nằm ở rp_loan_bridge;
        # owner_project_id (hoá đơn CĐT) nằm ở rp_owner_contract.
        'rp_loan_bridge',
        'rp_owner_contract',
    ],
    'data': [
        'views/account_move_views.xml',
    ],
    'installable': True,
    'application': False,
}
