# -*- coding: utf-8 -*-
{
    'name': 'EAMOne — Hiệu suất tổ máy theo ngày',
    'version': '19.0.1.0.0',
    'category': 'EAMOne',
    'summary': 'Một dòng cho mỗi tua-bin / bộ biến tần, mỗi ngày — để '
               'trả lời được "máy nào đang kéo cả trại xuống".',
    'description': """
EAMOne — Hiệu suất tổ máy theo ngày
====================================

Khối chiếm nửa tờ báo cáo
--------------------------
Tờ báo cáo ngày của nhà máy điện gió dành nửa trang cho bảng hai mươi
sáu tua-bin; tờ điện mặt trời dành một khối tương tự cho mười chín bộ
biến tần. **Cùng một hình dạng** — mỗi dòng một máy, mỗi cột một chỉ
tiêu, cuối bảng một dòng TỔNG — nên bảng này dựng một lần, dùng cho cả
hai công nghệ. Phần riêng của từng ngành do gói ngành thêm vào.

Câu hỏi nó trả lời
-------------------
Con số cấp nhà máy trả lời *"hôm qua trại phát bao nhiêu"*. Bảng này
trả lời câu người vận hành hỏi mỗi sáng: ***máy nào đang kéo cả trại
xuống***. Muốn trả lời thì phải so được giữa các máy, xếp hạng được,
nhìn được xu hướng nhiều ngày — tính lúc in thì không làm được gì
trong số đó.

Tổ máy phải KHAI, không đoán
-----------------------------
Cây vị trí chứa cả thứ không phát điện: trạm khí tượng, nhà điều hành,
trạm biến áp. Đếm bừa "mọi vị trí thiết bị" là đưa trạm khí tượng vào
bảng — đúng cái đã dính ở khả dụng nhà máy điện mặt trời: mười sáu bộ
biến tần thành mười bảy đơn vị, và con số vẫn nằm trong khoảng 0–100%
nên không ai nghi.

Có nút **gợi ý** (vị trí nào có điểm đo điện năng thì gần như chắc chắn
là tổ máy), nhưng nó đề xuất rồi báo đã làm gì — người xác nhận, máy
không tự quyết. Và hệ đối chiếu số tổ máy đã khai với số đơn vị dùng
cho mẫu số khả dụng: lệch thì **nói ra**, không chọn hộ một trong hai.

HAI chỉ số khả dụng, và vì sao không gộp
-----------------------------------------
Trên tờ báo cáo thật, một tua-bin ghi khả dụng **38,08%** ở cột của nhà
máy và **79,68%** ở cột của nhà sản xuất. Khoảng cách ấy không phải lỗi
— nó là **phạm vi trách nhiệm**: hãng loại trừ những nguyên nhân không
thuộc về họ, ta thì tính hết vì ta mất sản lượng thật.

Gộp hai cột là xoá mất chỗ để cãi nhau với nhà thầu. Nên cột của ta
**đo được** từ sổ dừng máy; cột của hãng **nhập vào** từ báo cáo của
họ; và hệ in luôn khoảng lệch, vì khoảng lệch mới là thứ đưa ra bàn
họp. Dựng lại bảng KHÔNG xoá cột nhập tay.

Dùng lại engine, không tính lần hai
------------------------------------
Khả dụng theo sản lượng gọi **đúng engine của sổ khả dụng nhà máy**,
chỉ đổi phạm vi từ nhà máy xuống tổ máy. Hai nơi cùng tính "sản lượng
đáng lẽ phát được" là hai nơi sớm muộn ra hai số.

Dòng TỔNG không phải trung bình các phần trăm
----------------------------------------------
Một tua-bin dừng cả ngày giữa mùa lặng gió và một tua-bin dừng cả ngày
giữa mùa gió mạnh mất lượng điện khác hẳn nhau. Khả dụng toàn trại cộng
TỬ SỐ và cộng MẪU SỐ rồi mới chia. Riêng cột của hãng là số nhập, không
có tử/mẫu để cộng — nên nó là trung bình, và hệ nói rõ nó không cùng
loại với cột bên trái.

Chưa đo được thì nói, không ghi 0
----------------------------------
Chưa khai công suất định mức thì hệ số công suất để trống kèm lý do:
chia cho một con số đoán bừa ra tỷ lệ trông hợp lý và sai. Luỹ kế tháng
chỉ cộng những ngày CÓ SỐ, và in kèm **số ngày đã cộng** — thiếu ngày
thì luỹ kế nhỏ hơn thật, và đó là thứ người đọc phải thấy.
""",
    'author': 'BSD Insight',
    'website': 'https://bsdinsight.com',
    'license': 'LGPL-3',
    'depends': ['eam_core', 'eam_historian', 'eam_downtime',
                'eam_availability'],
    'data': [
        'security/ir.model.access.csv',
        'data/eam_unit_day_cron.xml',
        'views/eam_unit_day_views.xml',
    ],
    'installable': True,
}
