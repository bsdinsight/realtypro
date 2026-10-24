# -*- coding: utf-8 -*-
{
    'name': 'EAMOne — Báo cáo vận hành ngày',
    'version': '19.0.1.0.0',
    'category': 'EAMOne',
    'summary': 'Máy rót sẵn tờ báo cáo ngày từ số đã có, người trực sửa '
               'chừng mười ô rồi chốt. Một bộ máy, nhiều hồ sơ cấu hình.',
    'description': """
EAMOne — Báo cáo vận hành ngày
===============================

Mỗi sáng, một tờ giấy
----------------------
Nhà máy nào cũng gửi một tờ báo cáo ngày. Hôm nay nó được gõ tay vào
bảng tính: người trực chép lại chừng sáu mươi con số mà **hệ đã có
sẵn**, rồi thêm vào vài câu nhận xét chỉ mình họ biết.

Phần chép tay ấy là chỗ sai số chui vào, và là lý do tờ báo cáo thường
không khớp với chính hệ sinh ra nó.

Lắp ráp, KHÔNG tính lại
------------------------
Mọi con số của một ngày đã nằm sẵn trong hệ: khí tượng ở sổ quan trắc,
sản lượng từng bậc ở chuỗi điểm đo, hiệu suất ở bảng PR, khả dụng ở sổ
khả dụng, giờ dừng ở sổ dừng máy. Module này **đi lấy**, chứ không tính
lần hai — có engine thứ hai là có hai con số cho cùng một ngày, và cuộc
họp sau đó bàn xem tin cái nào.

Một bộ máy, nhiều hồ sơ cấu hình
---------------------------------
Tờ của điện mặt trời và của điện gió khác nhau ở **nội dung từng dòng**,
không khác ở cách làm việc. Nên dòng trên tờ là dữ liệu: mỗi dòng khai
nhãn in ra, đơn vị, và lấy số từ đâu. Thêm loại nhà máy thứ ba là thêm
một hồ sơ, không đụng tới mã.

Ô người nhập tách khỏi ô máy tính
----------------------------------
Người trực chỉ chạm vào chừng mười ô: quan trắc bằng mắt, nhân sự, khách
đến, an toàn, nhận xét. Hệ **đếm** số ô ấy và hiện lên ngay trên hồ sơ
cấu hình — quá mười lăm ô thì tờ báo cáo quay về thành việc chép tay, và
người ta sẽ điền cho xong chứ không điền cho đúng.

Ô trống KHÁC số không
----------------------
*Chưa có số đo* và *đo được và bằng không* là hai chuyện khác hẳn nhau.
Ghi 0 cho cái chưa đo được thì tổng vẫn cộng ra, biểu đồ vẫn vẽ liền
mạch, và không ai biết hôm đó mất dữ liệu. Mỗi dòng mang cờ riêng kèm
**lý do**, và bản in ghi "—".

PR mà mẫu số còn lệch thì **không** lên tờ như một con số bình thường:
khoảng lệch đang treo chờ nhà máy trả lời, và báo cáo là chỗ cuối cùng
nên giấu chuyện đó.

Chốt rồi thì đóng băng; sửa thì ra BẢN MỚI
-------------------------------------------
Tờ đã chốt là bản ghi **những gì đã báo hôm đó**. Số liệu có thể đúng là
phải sửa — SCADA nạp lại, một khoảng dừng khai nhầm nhóm — nhưng sửa đè
lên tờ đã gửi đi là xoá mất chuyện ta đã từng báo thế nào. Sửa sinh ra
bản kế tiếp, trỏ ngược về bản cũ, kèm **lý do**; bản cũ chuyển sang "đã
thay thế" chứ không biến mất, và không xoá được.

Cron dựng, KHÔNG tự chốt
-------------------------
Sáng sớm hệ dựng sẵn tờ của hôm qua cho mọi nhà máy có hồ sơ. Dựng chứ
không chốt và không gửi: tờ báo cáo cần người trực xác nhận quan trắc và
nhận xét. Tự gửi một tờ chưa ai đọc là biến báo cáo ngày thành thư rác
trong ba ngày.
""",
    'author': 'BSD Insight',
    'website': 'https://bsdinsight.com',
    'license': 'LGPL-3',
    'depends': ['eam_core', 'eam_chain', 'eam_solar', 'eam_downtime',
                'eam_availability', 'eam_historian', 'eam_work_order'],
    'data': [
        'security/ir.model.access.csv',
        'data/eam_daily_profile_pv.xml',
        'data/eam_daily_profile_wind.xml',
        'data/eam_daily_report_cron.xml',
        'report/eam_daily_report_report.xml',
        'views/eam_location_views.xml',
        'views/eam_daily_profile_views.xml',
        'views/eam_daily_report_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
