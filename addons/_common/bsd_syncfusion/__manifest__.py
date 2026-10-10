# -*- coding: utf-8 -*-
{
    'name': 'BSD — Syncfusion EJ2 (lớp dùng chung)',
    'version': '19.0.1.0.0',
    'category': 'Technical',
    'summary': 'Thư viện Syncfusion EJ2 rút gọn, nạp theo yêu cầu, dùng '
               'chung cho mọi sản phẩm BSD.',
    'description': """
Lớp Syncfusion dùng chung
=========================

Trước đây thư viện, bộ nạp và khoá giấy phép nằm trong ``rp_progress``
— một module của EPCOne. EAMOne muốn dùng cùng thư viện thì phải phụ
thuộc ngược lên EPCOne: ``_common`` phụ thuộc ``_project`` là **lộn
ngược tầng**, và một khách chỉ mua EAMOne sẽ bị kéo theo cả phân hệ
nghiệm thu khối lượng mà họ không dùng.

Module này giữ ba thứ dùng chung:

* **Thư viện** ``ej2-slim.min.js`` — bản rút gọn còn Gantt, Charts,
  TreeGrid và cây phụ thuộc, dựng lại được bằng
  ``scripts/build_syncfusion_slim.py``. Bản global của Syncfusion gộp
  mọi component (spreadsheet, pdfviewer, diagram, maps…) nên nặng
  28,8 MB; bộ này chỉ dùng vài thứ nên còn 8,1 MB / 1,72 MB sau nén.
* **Bộ nạp theo yêu cầu** ``loadEj2()``. Để lib trong
  ``web.assets_backend`` thì MỌI trang Odoo — form khách hàng, danh
  sách hoá đơn, vừa đăng nhập xong — đều phải tải và phân tích chừng đó
  mã dù cả phiên không ai mở Gantt; mỗi lần nâng cấp module lại đổi
  hash nên tải lại từ đầu, và màn hình quay hàng chục giây.
* **Khoá giấy phép** qua controller, lấy từ tham số hệ thống
  ``syncfusion.license_key``. Thêm ``loadEj2WithLicense()`` gom việc
  nạp và đăng ký khoá về một chỗ — trước đó bốn nơi tự chép lại cùng
  một đoạn, mà chỉ cần một bản quên xử lý trường hợp chưa khai khoá là
  chỗ đó hiện watermark "trial" giữa màn hình khách hàng.

Route cũ ``/rp_progress/syncfusion/license_key`` được **giữ nguyên** làm
lối tương thích: trình duyệt đang mở vẫn ôm mã JS cũ trong bộ nhớ đệm và
sẽ gọi địa chỉ đó.
""",
    'author': 'BSD Insight',
    'website': 'https://bsdinsight.com',
    'license': 'AGPL-3',
    'depends': ['web'],
    'assets': {
        # Bundle RIÊNG, KHÔNG nằm trong web.assets_backend — nạp theo
        # yêu cầu qua loadEj2().
        'bsd_syncfusion.assets_syncfusion': [
            'bsd_syncfusion/static/lib/syncfusion/ej2-slim-material.css',
            'bsd_syncfusion/static/lib/syncfusion/ej2-slim.min.js',
        ],
        'web.assets_backend': [
            'bsd_syncfusion/static/src/js/ej2_loader.js',
        ],
    },
    'installable': True,
}
