# -*- coding: utf-8 -*-
{
    'name': 'EAMOne — Bản đồ hiện trường',
    'version': '19.0.1.0.0',
    'category': 'EAMOne',
    'summary': 'Cắm thiết bị lên ảnh vệ tinh, tô màu theo trạng thái thật '
               'và soi khoảng giãn cách.',
    'description': """
Bản đồ hiện trường
==================

Một màn hình gom tất cả: vị trí thiết bị trên ảnh vệ tinh, **tô màu theo
trạng thái đang xảy ra**, kèm khả dụng, sản lượng mất, lệnh công việc
đang mở và thiết bị đang lắp — bấm vào từng điểm là ra.

Bốn điều đáng nói
-----------------

**① Toạ độ KHÔNG nằm ở lõi.** "Vị trí hộp số bên trong tua-bin T07" là
một vị trí chức năng hợp lệ nhưng không có toạ độ nào có nghĩa — nó nằm
trong vỏ máy, cao 120 m. Chỉ vị trí cấp nhà máy và cấp thiết bị mới cắm
được lên bản đồ. Nhét kinh vĩ độ vào lõi là mời mọi người điền bừa cho
đủ ô.

**② Màu suy từ khoảng dừng ĐANG MỞ, không khai tay.** Không có khoảng mở
nào thì coi như đang phát. Đây là một **giả định**, không phải sự thật:
nó chỉ đúng khi sổ dừng máy được ghi đầy đủ. *Độ bao phủ của sổ* bên
``eam_energy`` là chỗ kiểm lại điều đó, nên hai màn hình phải đọc cùng
nhau — một bản đồ toàn màu xanh với độ bao phủ 60% nghĩa là bản đồ đang
nói dối.

Khi một vị trí có nhiều khoảng mở cùng lúc (vừa hỏng vừa bị cắt giảm),
màu lấy theo **thứ tự ưu tiên của loại thời gian**, đúng cơ chế phân xử
của chuẩn, chứ không lấy bản ghi mới nhất.

**③ Vòng giãn cách là phép ĐƠN GIẢN HOÁ, và module nói thẳng điều đó.**
Dòng khí sau một tua-bin có HƯỚNG: thực tế cần giãn 7–10D xuôi gió nhưng
chỉ 3–5D ngang gió. Một vòng tròn bán kính cố định không phân biệt được,
và không có hoa gió của chính khu đất thì không tính đúng được. Vòng vẽ
bán kính bằng **nửa** khoảng giãn yêu cầu, nên *hai vòng chạm nhau đúng
bằng ngưỡng* và chồng nhau là quá gần. Con số này để **soi chỗ đáng
ngờ**, không để kết luận — dòng chữ đó nằm ngay trên màn hình, không
giấu trong tài liệu.

**④ Toàn bộ dữ liệu về trong MỘT lần gọi.** Gọi từng điểm thì 30 thiết bị
thành 30 vòng truy vấn, và bản đồ giật mỗi lần kéo.

Thư viện bản đồ nhúng sẵn trong module, không gọi dịch vụ ngoài. Ảnh nền
vệ tinh và địa hình tải thẳng từ trình duyệt người dùng.

Dùng được cho mọi ngành
-----------------------
Module chỉ phụ thuộc lõi EAM và lệnh công việc; phần sản lượng mất và
cách tính tiền được **dò mềm** — có thì hiện, không có thì thôi. Nhà máy
nước, trạm biến áp, đội xe hay dây chuyền nhà xưởng dùng cùng một màn
hình này, chỉ khác cái vòng giãn cách vốn là chuyện riêng của điện gió.
""",
    'author': 'BSD Insight',
    'website': 'https://bsdinsight.com',
    'license': 'AGPL-3',
    'depends': ['eam_core', 'eam_work_order'],
    'data': ['views/eam_map_views.xml'],
    'assets': {
        'web.assets_backend': [
            'eam_map/static/lib/leaflet/leaflet.css',
            'eam_map/static/src/scss/eam_map.scss',
            'eam_map/static/src/js/eam_map.js',
            'eam_map/static/src/xml/eam_map.xml',
        ],
    },
    'installable': True,
}
