# -*- coding: utf-8 -*-
{
    'name': 'Đối soát ngân hàng — gom vào Quản lý Vay',
    'version': '19.0.1.0.0',
    'category': 'Accounting/Treasury',
    'summary': 'Đưa Giao dịch ngân hàng vào nhóm "Trích thu & Thanh toán" '
               'thay vì đứng riêng một menu gốc.',
    'description': """
Vì sao cần một module riêng chỉ để dời menu
===========================================

``re_bank_sync`` cố ý **không biết tới phân hệ Vay** — nó là sổ đệm giao
dịch ngân hàng, nguồn nào đổ vào cũng được. Còn ``re_loan`` thì không
biết tới ``re_bank_sync``. Khai lệnh dời menu ở bên nào cũng tạo ra một
phụ thuộc không nên có, và sẽ làm vỡ lúc cài module kia một mình.

Nên lệnh dời nằm ở đây, với ``auto_install = True``: hễ có đủ cả hai thì
tự bật, không có thì không tồn tại.

Đã có ``re_treasury_menu`` gom menu rộng hơn (đổi tên gốc thành "Vốn &
Ngân quỹ", gom cả Bảo lãnh và Ngân quỹ). Module này **không thay thế**
nó, chỉ làm đúng một việc hẹp — vì ``re_treasury_menu`` kéo theo
``re_lease``, ``re_cashflow``, ``re_loan_borrowing_base``, tức là cài
thêm cả một mảng nghiệp vụ chỉ để dời một menu.

Người dùng thấy gì
------------------
"Đối soát ngân hàng" đang đứng riêng ở menu gốc, trong khi việc của nó —
đối chiếu tiền ngân hàng với khoản phải thu/phải trả — luôn làm liền tay
với trích thu và giấy báo nợ. Gom lại thì còn một chỗ để nhìn thay vì
hai menu gốc cạnh nhau.
""",
    'author': 'BSD Insight',
    'website': 'https://bsdinsight.com',
    'license': 'AGPL-3',
    'depends': ['re_loan', 're_bank_sync'],
    'data': ['views/menu.xml'],
    'auto_install': True,
    'installable': True,
}
