# -*- coding: utf-8 -*-
{
    'name': 'Realty — Ký số CA (PAdES)',
    'version': '19.0.1.0.0',
    'category': 'Realty',
    'summary': 'Ký số lên file PDF theo chuẩn PAdES — kiểm tra được bằng '
               'Adobe Reader. Hỗ trợ ký số từ xa qua nhà cung cấp CA.',
    'description': """
Ký số CA (PAdES)
================

Nối tiếp ``re_sign``. Hai lớp khác nhau, đừng lẫn:

* ``re_sign`` — **chữ ký điện tử**: ký trong hệ thống, mã băm phát hiện
  sửa nội dung. Nhanh, không phụ thuộc ai, nhưng chỉ có giá trị TRONG
  hệ thống: gửi file ra ngoài thì không ai kiểm được.
* ``re_ca_sign`` (module này) — **chữ ký số**: ký lên chính file PDF
  theo chuẩn PAdES. Mở bằng Adobe Reader là thấy bảng chữ ký, biết ai
  ký, lúc nào, và **tài liệu có bị sửa sau khi ký hay không** — không
  cần Odoo.

Ba đường ký, chọn bằng tham số ``re_ca_sign.provider``:

1. ``test`` — chứng thư TỰ SINH ngay trong hệ thống. Toàn bộ cơ chế ký
   và kiểm tra là THẬT; chỉ thiếu mỗi việc chứng thư không do tổ chức
   chứng thực cấp, nên Adobe báo "chữ ký hợp lệ nhưng chưa tin cậy được
   người ký". Dùng để chạy thử và demo.
2. ``smartca`` — **ký số từ xa**: chứng thư nằm trong HSM của nhà cung
   cấp. Hệ thống gửi MÃ BĂM của tài liệu, người ký xác nhận trên điện
   thoại, nhà cung cấp trả chữ ký về. Khoá riêng KHÔNG bao giờ rời HSM.

   Đã nối **Viettel MySign** theo tài liệu tích hợp ký bất đồng bộ của
   Viettel-CA (chuẩn Cloud Signature Consortium): login →
   credentials/list → signHash → requests/status. Khai kết nối ở
   **Cài đặt ▸ Ký số CA ▸ Kết nối nhà cung cấp**.

   Bản khai chỉ dùng được sau khi bấm *Kiểm tra kết nối* và lấy được
   chứng thư thật về — khai đủ ô mà chưa kiểm thì hệ thống từ chối ký,
   có chủ ý: một màn cấu hình trông như đã nối là thứ nguy hiểm nhất
   lúc demo.

   Các nhà cung cấp khác (VNPT SmartCA, FPT.eSign) cùng chuẩn CSC nên
   khác chủ yếu ở đường dẫn và tên trường — thêm một giá trị vào ô
   *Nhà cung cấp* là nối được.
3. ``token`` — token USB cắm ở máy người ký. **Máy chủ không với tới
   được**: phải có phần mềm ký chạy trên chính máy đó. Để đây cho đủ
   bản đồ, chưa làm.
""",
    'author': 'BSD Insight',
    'website': 'https://realtypro.vn',
    'license': 'LGPL-3',
    'depends': ['re_sign'],
    'external_dependencies': {'python': ['pyhanko']},
    'data': [
        'security/ir.model.access.csv',
        'views/re_ca_config_views.xml',
        'views/re_ca_provider_views.xml',
        'views/re_ca_signature_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
