# -*- coding: utf-8 -*-
{
    'name': 'EAMOne — Mua sắm phụ tùng',
    'version': '19.0.1.0.0',
    'category': 'EAMOne',
    'summary': 'Nối sổ tài sản EAMOne vào chuỗi Mua sắm của Realty và '
               'vào kho.',
    'description': """
Cầu nối, không phải tính năng
=============================

Module này tồn tại để Realty **không** phải phụ thuộc EAMOne, và EAMOne
**không** phải phụ thuộc Realty. Ai cài cả hai thì cài thêm cầu này.

Hai việc nó làm
---------------

**① Phụ tùng đi đúng chuỗi, không mở đường riêng.**
Realty đã có chuỗi *Yêu cầu mua sắm → Đơn mua → Nhận hàng & nghiệm thu →
Đề nghị thanh toán*. Chuỗi này bọc ngoài app Mua hàng của Odoo và thêm
ba bước Odoo không có. Phụ tùng bảo trì **đi theo đúng chuỗi đó**, chỉ
khác là có thêm nguồn phát sinh: mua cho tài sản nào, hoặc cho loại cấu
phần nào.

Mở một đường mua riêng cho bảo trì là lập tức có hai cửa vào cùng một
``purchase.order`` với hai bộ luật khác nhau — và người ta sẽ đi cửa
ngắn.

**② Vật tư quay vòng BẮT BUỘC theo dõi theo sê-ri.**
Hộp số, máy phát, cánh, bộ biến đổi: tháo ra, đem đi đại tu, lắp lại.
Không theo sê-ri thì sau lần đại tu thứ hai không ai biết con nào đang
nằm ở đâu — mà đó chính là câu hỏi quyết định quyền đòi bảo hành.

Module chặn ở tầng ràng buộc: sản phẩm gắn với loại cấu phần quay vòng
mà để ``tracking`` khác ``serial`` thì không lưu được.
""",
    'author': 'BSD Insight',
    'website': 'https://bsdinsight.com',
    'license': 'AGPL-3',
    'depends': ['eam_core', 'rp_purchase', 'stock'],
    'data': [
        'views/eam_procurement_views.xml',
    ],
    'installable': True,
}
