# -*- coding: utf-8 -*-
{
    'name': 'EAMOne — Ký số chứng từ O&M',
    'version': '19.0.1.0.0',
    'category': 'EAMOne',
    'summary': 'Ký điện tử và ký số PAdES lên Báo cáo vận hành ngày và '
               'Biên bản xác nhận KPI/SLA.',
    'description': """
Ký số chứng từ O&M
==================

Module CẦU NỐI, và cố ý tách riêng. ``eam_daily_report`` với
``eam_om_contract`` KHÔNG phụ thuộc ``re_ca_sign``, vì ``re_ca_sign``
kéo theo ``pyhanko`` — bắt mọi khách EAMOne mang theo một thư viện ký số
chỉ để xem báo cáo ngày là vô lý. Ai cần ký thì cài module này.

Mở ký cho HAI chứng từ, và chỉ hai:

* **Báo cáo vận hành ngày** (``eam.daily.report``) — tờ giấy đi ra khỏi
  công ty mỗi ngày, tới chủ đầu tư. Đã có sẵn mẫu in.
* **Biên bản xác nhận KPI/SLA** (``eam.om.period``) — chứng từ làm căn
  cứ THANH TOÁN và PHẠT. Mẫu in dựng mới trong module này.

Không mở cho Lệnh công việc: đó là chứng từ nội bộ, ký số lên nó không
đổi được điều gì về mặt pháp lý. Cần thì mở sau, mỗi chứng từ thêm một
hàm ``_ca_report_ref``.

Hai luật chặn, viết vào code chứ không nhắc nhau:

1. **Chỉ ký được chứng từ ĐÃ CHỐT.** Ký một bản nháp là ký lên con số
   còn đổi được — chữ ký vẫn báo hợp lệ sau khi người ta rót lại số.
2. **Kỳ KPI còn cảnh báo thì không ký được.** Cờ ``co_canh_bao`` nghĩa
   là có dòng chưa đo được, hoặc giờ dừng chưa quy trách nhiệm vượt
   ngưỡng — con số khả dụng đang đẹp vì chưa ai phân loại. Ký lên đó là
   đóng dấu vào một con số sẽ đổi.
""",
    'author': 'BSD Insight',
    'website': 'https://realtypro.vn',
    'license': 'LGPL-3',
    'depends': [
        'eam_daily_report',
        'eam_om_contract',
        're_ca_sign',
    ],
    'data': [
        'report/eam_om_period_report.xml',
        'views/eam_daily_report_views.xml',
        'views/eam_om_period_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
