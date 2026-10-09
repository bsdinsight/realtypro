# -*- coding: utf-8 -*-
{
    'name': 'EPCOne ↔ EAMOne — Cầu bàn giao',
    'version': '19.0.1.0.0',
    'category': 'EPCOne',
    'summary': 'Chuyển công trình đã nghiệm thu thành tài sản vận hành, '
               'giữ nguyên đồng hồ bảo hành của từng vị trí.',
    'description': """
Cầu bàn giao dự án → tài sản
============================

Khúc không ai sở hữu
--------------------
Phần mềm quản lý dự án dừng ở ngày vận hành thương mại. Phần mềm quản lý
tài sản bắt đầu từ đó. Giữa hai bên là một cuộc **gõ lại bằng tay vài
trăm bản ghi** — và mọi cuộc bàn giao EPC sang O&M trên đời đều mất dữ
liệu ở đúng khúc này.

Thứ mất đi đắt nhất là **đồng hồ bảo hành**: ba năm sau hộp số hỏng,
không ai trả lời nổi *con này do ai cấp, theo hợp đồng nào, bảo hành tới
khi nào*.

Năm quyết định thiết kế
-----------------------

**① Bàn giao theo TỪNG VỊ TRÍ, không theo cả dự án.** Nhà máy điện gió
bàn giao từng trụ một: trụ số 1 xong trước trụ số 30 có khi tám tháng.
Gộp thành một mốc "COD" duy nhất là xoá mất đồng hồ bảo hành riêng của
từng trụ — thứ đắt nhất trong cả cuộc bàn giao.

**② Bảo hành chạy từ ngày nghiệm thu của CHÍNH trụ đó**, lấy từ cổng
nghiệm thu trong sổ dựng máy. Trước bàn giao, cả đội máy dùng chung một
ngày hết hạn; sau bàn giao, mỗi trụ một ngày.

**③ Bàn giao là NỐI DẤU VẾT, không phải chép dữ liệu.** Tài sản giữ
đường về: lô thiết bị nào, hợp đồng nào, nhà cung cấp nào, biên bản nào
chuyển. Chép xong mà không nối thì vẫn phải đi khảo cổ.

**④ Được phép bàn giao khi còn THIẾU, nhưng phải nói ra thiếu gì.**
Sê-ri thường chưa có lúc bàn giao vì nhà thầu chưa nộp hồ sơ hoàn công.
Chặn tới khi đủ thì bàn giao không bao giờ xảy ra; cho qua im lặng thì
chỗ thiếu không bao giờ được điền. Nên mỗi dòng có **độ đầy đủ** và cột
**còn thiếu** ghi tên từng thứ.

**⑤ Mã không khớp phải BÁO.** Sổ lô thiết bị ghi ``WTG-01``, vị trí chức
năng ghi ``T01`` — hai hệ đặt tên khác nhau là chuyện thường. Hệ thống
khớp theo phần số đứng cuối, và cái nào không khớp thì **liệt kê ra**
chứ không lặng lẽ bỏ qua.

Bàn giao làm bốn việc
---------------------
Việc nào thiếu cũng làm hỏng một câu hỏi về sau:

* đặt **ngày vận hành và hạn bảo hành theo nghiệm thu của chính trụ này**
  — không có thì cả đội máy dùng chung một ngày hết hạn;
* ghi **nguồn gốc** trỏ về lô thiết bị, hợp đồng, biên bản — không có
  thì ba năm sau phải đi khảo cổ;
* dựng **đồng hồ giờ máy** bắt đầu từ 0 — không có thì mọi kế hoạch bảo
  trì theo giờ im lặng không bao giờ tới hạn;
* **áp lịch bảo trì** với mốc tính từ ngày bàn giao — không có thì chu
  kỳ đầu tiên đếm từ ngày lắp, tức đã quá hạn ngay khi nhận máy.

Và **không quay lui được** sau khi bàn giao: đó là mốc pháp lý, lùi lại
sẽ làm đồng hồ bảo hành đã chạy biến mất mà không ai biết.
""",
    'author': 'BSD Insight',
    'website': 'https://bsdinsight.com',
    'license': 'AGPL-3',
    'depends': ['eam_pm', 'rp_erection', 'rp_equipment', 'rp_contract',
                'rp_site_map'],
    'data': [
        'security/ir.model.access.csv',
        'data/rp_handover_sequence.xml',
        'views/rp_handover_views.xml',
    ],
    'installable': True,
}
