# -*- coding: utf-8 -*-
{
    'name': 'EAMOne — Theo dõi tiến độ bảo trì',
    'version': '19.0.1.0.0',
    'category': 'EAMOne',
    'summary': 'Kế hoạch so với thực tế, kanban, lịch, tải theo người — '
               'và đẩy cảnh báo trễ hạn ra người phụ trách thay vì chờ '
               'họ mở màn hình.',
    'description': """
EAMOne — Theo dõi tiến độ bảo trì
==================================

Dữ liệu đã có, thiếu chỗ nhìn — và thiếu cú ĐẨY
------------------------------------------------
Lệnh công việc đã mang đủ bốn mốc: dự kiến bắt đầu, dự kiến xong, thực
tế bắt đầu, thực tế xong. Thứ thiếu là **đặt chúng cạnh nhau**, và quan
trọng hơn: **nói cho người phụ trách biết khi trễ**. Lệnh trễ mà không
ai mở màn hình thì nó trễ tiếp.

Ba quyết định
-------------

**① "Đang trễ hạn" là trường THƯỜNG, không phải trường tính.** Câu hỏi
*đã quá hạn chưa* phụ thuộc vào **bây giờ là mấy giờ**, mà thời điểm
hiện tại không nằm được trong ``@api.depends``. Khai thành trường tính
có lưu thì Odoo không bao giờ thấy lý do tính lại, và cờ đứng yên mãi ở
giá trị lúc tạo — sai im lặng, màn hình không báo gì. Đã dính đúng kiểu
này ở hạn nghĩa vụ và ở tổn thất bậc thang. Nên ở đây cron cập nhật:
lọc được, cộng được, và không giả vờ tự biết.

**② Trễ vì bị bỏ quên KHÁC trễ vì đang chờ.** Một lệnh quá hạn vì chờ
phụ tùng chưa về là vấn đề của chuỗi cung ứng, không phải của người thợ.
Nhắc họ mỗi ngày về chuyện họ không giải quyết được là cách nhanh nhất
khiến họ bỏ qua mọi thông báo về sau. Hai loại tách riêng, và **chỉ loại
bị bỏ quên mới đẩy thông báo**.

**③ Không nhắc lại mỗi ngày.** Cron chạy hằng ngày nhưng chỉ đẩy khi
vượt một **nấc mới**: vừa quá hạn, rồi ba ngày, rồi bảy ngày. Nhắc mỗi
ngày thì sau một tuần người ta lọc hết thông báo vào thùng rác, và lúc
có lệnh thật sự gấp thì không ai nhìn.

Thông báo đi vào **việc cần làm** của người phụ trách, không gửi thư
điện tử: thư trôi mất giữa hàng trăm thư khác, còn việc cần làm nằm ngay
trong màn làm việc hằng ngày và có người đóng nó lại.

Nói thẳng về Gantt
-------------------
Odoo Community **không có view gantt** — ``web_gantt`` thuộc bản
Enterprise. Nên "kế hoạch so với thực tế trên cùng một trục" ở đây dựng
bằng cột: bốn mốc đặt cạnh nhau cộng ba con số lệch tính sẵn. Thông tin
đủ để trả lời *bắt đầu trễ bao lâu, xong trễ bao lâu, làm lâu hơn dự
tính bao nhiêu*; chỉ là không vẽ thành thanh.

Muốn thanh thật thì dùng lại thành phần gantt tự viết bên phần dự án —
nhưng nó kéo theo thư viện vẽ và buộc phần vận hành phụ thuộc phần dự
án, nên đó là một quyết định kiến trúc riêng, không phải chuyện giao
diện.
""",
    'author': 'BSD Insight',
    'website': 'https://bsdinsight.com',
    'license': 'LGPL-3',
    'depends': ['eam_work_order'],
    'data': [
        'data/eam_wo_progress_cron.xml',
        'views/eam_wo_progress_views.xml',
    ],
    'installable': True,
}
