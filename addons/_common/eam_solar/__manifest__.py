# -*- coding: utf-8 -*-
{
    'name': 'EAMOne — Điện mặt trời',
    'version': '19.0.1.0.0',
    'category': 'EAMOne',
    'summary': 'Cây cấu phần quang điện, nhật ký khí tượng ngày, và tỷ số '
               'hiệu suất PR/PA theo IEC 61724-1 — công thức khai được '
               'theo từng nhà máy.',
    'description': """
EAMOne — Điện mặt trời
=======================

Ba phần, đi cùng nhau vì không phần nào đứng một mình có nghĩa.

**1. Cây cấu phần quang điện**

Không có chuẩn phân loại công khai nào cho điện mặt trời tương đương
ReliaWind của điện gió, nên cây này dựng theo **đường đi của dòng điện**:
tấm pin → chuỗi → hộp gom → bộ biến tần → phía xoay chiều. Đi theo
dòng điện thì quy lỗi về đúng cấu phần dễ hơn hẳn so với chia theo nhà
cung cấp hay theo vị trí địa lý. Thêm hệ xoay và trạm khí tượng.

Trạm nâng áp, cáp ngầm và SCADA **không** nằm ở đây — chúng thuộc nhánh
BOP dùng chung cho mọi loại nhà máy.

**2. Nhật ký khí tượng ngày**

Một bản ghi mỗi ngày mỗi nhà máy, trộn hai thứ khác bản chất: số đo máy
đọc được và quan sát bằng mắt của người trực tại 6h, 9h, 12h, 15h. Trộn
là đúng vì chúng cùng mô tả một ngày, nhưng tách rõ ô nào của ai — và
khi người sửa đè lên số máy lấy thì bản ghi tự đánh dấu lại.

**3. Tỷ số hiệu suất và khả dụng**

Công thức theo IEC 61724-1, nhưng **ba thứ trong đó khai được theo từng
nhà máy**: lấy bức xạ từ cảm biến nào, mấy cảm biến thì trung bình, và
nhiệt độ tham chiếu để hiệu chỉnh nhiệt. Viết cứng một cách tính là đúng
cho nhà máy đầu tiên và sai cho mọi nhà máy sau — mà cái sai đó hiện lên
màn hình y hệt cái đúng.

Đã đối chiếu với báo cáo thật của một nhà máy đang vận hành: hai phần
khớp chính xác (``E danh định = tổng xạ × diện tích``, và
``PR = AC ÷ mẫu số`` ra đúng tới hai chữ số thập phân). Hai phần còn
lệch — mẫu số cao hơn 2,53% và nhiệt độ tham chiếu ứng với ~26,1 °C —
nên có ô **ghi đè mẫu số** kèm **cờ báo lệch**, để nhà máy nhập đúng số
của họ mà khoảng cách vẫn hiện ra thay vì bị giấu.

Hằng số được **chụp lại** vào từng bản ghi KPI chứ không tham chiếu
sống: sửa hằng số của nhà máy hôm nay không được làm đổi KPI đã tính của
tháng trước.
""",
    'author': 'BSD Insight',
    'website': 'https://bsdinsight.com',
    'license': 'LGPL-3',
    'depends': ['eam_core', 'eam_historian', 'eam_attr'],
    'data': [
        'security/ir.model.access.csv',
        'data/eam_solar_category_data.xml',
        'views/eam_solar_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
