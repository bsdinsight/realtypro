# -*- coding: utf-8 -*-
{
    'name': 'EAMOne — Hạch toán giờ dừng máy',
    'version': '19.0.1.0.0',
    'category': 'EAMOne',
    'summary': 'Ánh xạ 23 loại thời gian chuẩn sang nhóm báo cáo, quy giờ '
               'dừng ra kWh bằng máy đối chứng rồi ra tiền theo biểu giá.',
    'description': """
EAMOne — Hạch toán giờ dừng máy
================================

Sổ dừng máy đã ghi *bao nhiêu giờ, ở đâu, lỗi gì, ai chịu*. Module này
trả lời ba câu tiếp theo, và cả ba đều là chỗ báo cáo năng lượng hay nói
sai.

**① Hai mươi ba loại chuẩn, sáu dòng báo cáo.** Chuẩn IEC 61400-26 chia
thời gian thành 23 loại có cây và có thứ tự ưu tiên — thứ dùng để hạch
toán cho đúng. Tờ báo cáo khách đọc mỗi sáng chỉ có sáu dòng. Lưu theo
chuẩn, hiện theo nhóm, và phép ánh xạ là **dữ liệu** vì báo cáo điện gió
gộp khác điện mặt trời. Loại chưa ánh xạ ra một dòng *"chưa xếp nhóm"*
thay vì biến mất — tổng sáu dòng nhỏ hơn tổng thật mà không ai báo thiếu
là cách im lặng nhất để một báo cáo nói sai.

**② Quy giờ ra kWh bằng MÁY ĐỐI CHỨNG, không phải công suất định mức.**
``công suất định mức × số giờ dừng`` là cách nói sai phổ biến nhất trong
ngành: nó giả định suốt thời gian dừng lẽ ra chạy hết tải, trong khi gió
có thể lặng và trời có thể mưa. Con số ra luôn lớn hơn thực tế, lớn một
cách có lợi cho bên đi đòi — nên không đứng được trước nhà thầu.

Cách dùng ở đây: trong đúng khoảng máy X dừng, xem các máy anh em cùng
nhà máy cùng loại **đang chạy** phát được bao nhiêu, lấy trung bình. Điều
kiện gió nắng do chính các máy kia đo hộ. Cần ít nhất ba máy đối chứng —
một máy thì trung bình chính là máy đó, và nếu nó gặp sự cố cục bộ thì
cả phép tính lệch theo mà không có gì báo.

Ba trường hợp **nói thật thay vì trả một con số**: kho chuỗi thời gian
chưa có số đo trong khoảng đó; mọi máy anh em cũng đang dừng; khoảng
dừng ghi ở cấp nhà máy chứ không phải cấp tổ máy. Cả ba giữ nguyên con
số cũ và ghi lý do — **"không tính được" khác hẳn "bằng 0"**, vì 0 kWh
đọc ra là "lần dừng này không mất gì".

Và nút tính **không tự chạy lúc tạo bản ghi**: nhiều khoảng đã có số do
người vận hành gõ từ báo cáo nhà thầu, tự đè lên là xoá mất con số hai
bên đã cùng nhìn. Ô *"sản lượng mất lấy từ đâu"* giữ lại gốc gác, vì số
người gõ và số máy tính có sức nặng rất khác khi đem đi đòi.

**③ Hai cách tính giờ vận hành.** Tờ báo cáo thật ghi cả hai, sát nhau::

    System Operational hours            11,75 h
    System Operational hours (for PR)   11,47 h
    Curtailment Outage                   0,28 h

Chênh đúng bằng giờ cắt giảm. Khi lưới yêu cầu giảm phát, nhà máy **vẫn
sẵn sàng**: giờ đó tính vào giờ vận hành khi đánh giá nhà thầu, nhưng
không được vào mẫu số tỷ số hiệu suất — hiệu suất hỏi *"nắng vào bao
nhiêu thì ra bao nhiêu điện"*, và trong giờ bị cắt giảm câu đó vô nghĩa.
Lấy nhầm thì hiệu suất lệch đúng bằng tỷ lệ giờ cắt giảm: vài phần trăm,
đủ để một hợp đồng đạt thành không đạt.

Một engine, không phải hai
---------------------------
"Sản lượng đáng lẽ phát được" bị hỏi ở hai nơi: sổ dừng máy hỏi *lần
dừng này mất bao nhiêu*, khả dụng theo sản lượng hỏi *cả kỳ đáng lẽ phát
bao nhiêu*. Cùng một phép tính. Nên nó nằm trong **một file duy nhất**
và module khả dụng làm sau sẽ gọi vào đây, không viết hàm thứ hai — bài
học đã trả giá ở hai engine EVM.
""",
    'author': 'BSD Insight',
    'website': 'https://bsdinsight.com',
    'license': 'LGPL-3',
    'depends': ['eam_core', 'eam_historian'],
    'data': [
        'security/ir.model.access.csv',
        'data/eam_time_group_data.xml',
        'views/eam_downtime_views.xml',
    ],
    'installable': True,
}
