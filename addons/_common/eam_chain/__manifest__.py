# -*- coding: utf-8 -*-
{
    'name': 'EAMOne — Chuỗi điểm đo & tổn thất bậc thang',
    'version': '19.0.1.0.0',
    'category': 'EAMOne',
    'summary': 'Khai các bậc điện đi qua từ thiết bị phát tới công-tơ bán '
               'điện; tổn thất từng bậc, luỹ kế tháng/năm, đối chiếu '
               'công-tơ với SCADA.',
    'description': """
EAMOne — Chuỗi điểm đo & tổn thất bậc thang
============================================

Điện đi từ thiết bị phát tới công-tơ bán điện qua nhiều bậc, và mỗi bậc
ăn mất một ít. Tờ báo cáo vận hành ngày của **cả điện gió lẫn điện mặt
trời** đều có đúng khối này, chỉ khác tên bậc::

    mặt trời:  inverter → thanh cái → ranh giới → công-tơ bán điện
    điện gió:  tua-bin  → trạm 331  → máy biến áp nâng áp → điểm đấu nối

Cách KHÔNG làm là viết cứng năm dòng cộng trừ cho nhà máy đầu tiên. Nhà
máy thứ hai có bốn bậc tên khác, thế là viết lại; tới nhà máy thứ ba thì
có ba đoạn mã gần giống nhau và không ai dám sửa cái nào.

Ở đây **chuỗi là dữ liệu**: khai bậc, khai thứ tự, khai mỗi bậc lấy số
từ đâu. Tổn thất là hiệu giữa hai bậc liền kề — một phép tính duy nhất
chạy cho mọi nhà máy, mọi công nghệ.

Ba loại bậc, và vì sao phải tách
---------------------------------
Không phải chênh lệch nào cũng là tổn thất. **Điện tự dùng** và **tiêu
thụ ban đêm** là tiêu thụ có chủ đích, không phải thất thoát. Gộp chúng
vào tổn thất kỹ thuật thì con số tổn thất phồng lên mà không ai truy
được tại sao — và đó đúng là con số đi vào đánh giá nhà thầu O&M.

Luỹ kế không lưu
-----------------
Luỹ kế tháng và năm tính lại mỗi lần đọc. Lưu thì nhanh hơn, nhưng sửa
một ngày giữa tháng là mọi ngày sau nó sai cho tới khi có ai nhớ chạy
lại — mà sẽ không ai nhớ.

Dùng lại phần đã có
--------------------
Số đọc công-tơ sai phân **không viết mới**: ``eam.meter`` đã xử lý sẵn
hiệu hai số đọc liên tiếp, kể cả khi thay đồng hồ hoặc đồng hồ quay
vòng. Module này chỉ gọi vào.

Khép vòng với hiệu suất
------------------------
Ô "Điện năng AC" trên màn hiệu suất ngày trước nay phải nhập tay. Nó
chính là sản lượng tại bậc **công-tơ bán điện**, nên có nút lấy thẳng từ
đó. Vẫn cho sửa tay, vì nhà máy chưa khai chuỗi thì phải có đường nhập.
""",
    'author': 'BSD Insight',
    'website': 'https://bsdinsight.com',
    'license': 'LGPL-3',
    'depends': ['eam_core', 'eam_pm', 'eam_historian', 'eam_solar'],
    'data': [
        'security/ir.model.access.csv',
        'views/eam_chain_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
