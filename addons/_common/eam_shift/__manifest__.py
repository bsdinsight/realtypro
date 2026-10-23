# -*- coding: utf-8 -*-
{
    'name': 'EAMOne — Ca trực & giao ca',
    'version': '19.0.1.0.0',
    'category': 'EAMOne',
    'summary': 'Lịch ca, sơ đồ nhà máy đầu ca, việc trong ca và biên bản '
               'giao nhận — dựng quanh luật việc dở dang không được rơi '
               'giữa hai ca.',
    'description': """
EAMOne — Ca trực & giao ca
===========================

Thứ thật sự hỏng trong giao ca
-------------------------------
Không phải chuyện ai trực ca nào — bảng phân công thì nhà máy nào cũng
có, kể cả trên giấy. Thứ hỏng là **việc rơi giữa hai ca**: người ra ca
biết một chuyện, người vào ca không biết, và không ai viết xuống. Sáng
hôm sau máy hỏng nặng hơn, và cuộc truy nguyên dừng lại ở đúng một câu —
*"tôi không được bàn giao việc đó"*.

Module này dựng quanh một trục duy nhất: **không có gì được phép biến
mất giữa hai ca**.

Bốn quyết định
--------------

**① Việc dở dang chuyển sang ca sau, CÓ DẤU VẾT.** Đóng ca mà còn việc
chưa xong thì việc đó được tạo lại ở ca sau, trỏ ngược về bản gốc. Đi
ngược sợi dây ấy là đếm được một việc đã **lăn qua mấy ca** — và việc
lăn năm ca không phải việc khó, nó là việc **đang bị đùn**. Không có con
số này thì không ai nhìn thấy chuyện đó.

Cách sai mà phần mềm hay làm: chỉ hiện "các lệnh công việc còn mở". Nó
bỏ sót đúng những thứ hay rơi nhất — lời dặn miệng, cái vừa phát hiện
cuối ca chưa kịp lập lệnh, cái đang chờ nhà thầu trả lời. Những thứ đó
không phải lệnh công việc, nhưng chúng là phần lớn nội dung một cuộc
giao ca thật. Nên ở đây mỗi việc là một dòng **tự do**, nối tuỳ chọn
tới lệnh công việc nếu có.

**② Chụp trạng thái nhà máy lúc MỞ ca, không tính lại khi mở xem.** Mục
đích của sơ đồ đầu ca là *"người vào ca đã nhìn thấy gì"* — đó là bằng
chứng. Tính lại khi mở xem thì sáu tháng sau nó hiện trạng thái hôm nay,
và biên bản mất sạch giá trị. Cùng luật đã dùng cho hằng số hiệu suất và
cho kỳ hợp đồng đã chốt.

**③ Ký hai đầu, nhưng KHÔNG chặn vận hành.** Bàn giao chỉ một bên ký là
cái cớ kinh điển khi tranh chấp. Nhưng chặn đóng ca cho tới khi người
vào ca ký thì nhà máy không vì thế mà dừng — người ta sẽ ký hộ nhau, và
chữ ký mất luôn ý nghĩa. Nên cho đóng, nhưng **cắm cờ bàn giao một
chiều**, và cờ đó hiện ngay trên danh sách.

**④ Giao ca mà chưa có ca kế tiếp thì PHẢI nói.** Việc còn mở cần một
nơi để sang. Chưa sinh ca sau mà vẫn giao thì số việc đó không ai nhận —
hệ ghi thẳng cảnh báo vào nhật ký của ca thay vì im lặng.
""",
    'author': 'BSD Insight',
    'website': 'https://bsdinsight.com',
    'license': 'LGPL-3',
    'depends': ['eam_core', 'eam_work_order'],
    'data': [
        'security/ir.model.access.csv',
        'views/eam_shift_views.xml',
    ],
    'installable': True,
}
