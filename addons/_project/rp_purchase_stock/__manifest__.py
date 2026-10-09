# -*- coding: utf-8 -*-
{
    "name": "EPCOne — Mua sắm ↔ Kho",
    "version": "19.0.1.1.0",
    "category": "Realty/Project",
    "summary": "Nối phiếu nhập kho với biên bản nghiệm thu, và kho phụ "
               "tùng cho giai đoạn vận hành.",
    "description": """
Mua sắm ↔ Kho (rp_purchase_stock)
=================================

**Phiếu nhập kho KHÁC biên bản nghiệm thu.** Đây là chỗ hai hệ thống dễ
chồng cửa nhau nhất, và nếu để chồng thì hoặc người dùng nhập hai lần,
hoặc tiền đi ra mà không ai kiểm.

    Phiếu nhập kho   — hàng đã VÀO KHO. Việc của thủ kho, chỉ áp dụng
                       cho hàng lưu kho được.
    Biên bản nghiệm thu — hàng/dịch vụ ĐẠT YÊU CẦU và được phép trả tiền.
                       Việc của bộ phận kỹ thuật, áp dụng cho CẢ dịch vụ.

Hai việc khác nhau và không suy ra nhau: nhận đủ hàng vào kho rồi kiểm
tra không đạt là chuyện bình thường, và lúc đó vẫn không được trả tiền.
Ngược lại tư vấn giám sát thì nghiệm thu được mà chẳng nhập kho gì cả.

Nên module này KHÔNG gộp hai thứ. Nó chỉ **nối** chúng: biên bản ghi
được mình nghiệm thu cho những phiếu nhập nào, và từ phiếu nhập lập
thẳng được biên bản.

Tách thành module cầu nối riêng để `rp_purchase` vẫn chạy được ở bản
triển khai KHÔNG cài kho — phần lớn thứ chủ đầu tư mua trong giai đoạn
xây dựng là dịch vụ, không cần kho.
    """,
    "author": "BSDInsight",
    "website": "https://bsdinsight.com",
    "license": "AGPL-3",
    "depends": ["rp_purchase", "stock", "purchase_stock"],
    "data": [
        "views/rp_goods_receipt_views.xml",
        "views/stock_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
