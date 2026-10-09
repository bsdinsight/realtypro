# -*- coding: utf-8 -*-
{
    'name': 'EPCOne — Sổ dựng máy theo vị trí',
    'version': '19.0.1.0.0',
    'category': 'EPCOne',
    'summary': 'Tiến độ xây dựng tới TỪNG trụ, và phần trăm hạng mục suy '
               'ngược từ đó thay vì gõ tay.',
    'description': """
Sổ dựng máy
===========

Lịch của tổng thầu gom theo **lô vận chuyển** và **nhánh điện**: một việc
"Feeder 6 — 4 WTGS (10-13)" ôm bốn trụ. Đó không phải lỗi lập lịch mà là
cách họ thật sự thi công — ép lịch xuống từng trụ sẽ làm nó phình gấp mấy
lần mà vẫn không ai cập nhật nổi.

Nhưng quản lý lại cần biết **trụ số 7 đang kẹt ở đâu**. Nên cần một sổ
riêng, mịn hơn lịch một bậc: *mỗi vị trí × mỗi cổng = một ô*. Ngoài đời
site manager nào cũng giữ sổ này, thường bằng Excel.

Bốn quyết định thiết kế
-----------------------

**① Cổng có TRỌNG SỐ, không chia đều.** Đổ móng một trụ tua-bin 6 MW là
vài trăm mét khối bê tông và vài tuần; đấu một đầu cáp vào feeder là một
ngày. Đếm "7/9 cổng = 78%" coi mọi bước như nhau và vẽ ra đường cong
tiến độ không giống thực tế.

**② KHÔNG chặn khi qua cổng sau mà cổng trước chưa xong.** Không thể dựng
tháp trước khi đổ móng — nhưng chuyện đó xảy ra TRÊN SỔ suốt, vì người
ghi quên tích cổng móng chứ không phải vì họ dựng tháp lên bùn. Chặn thì
họ sẽ tích bừa cổng trước cho qua, và mất sạch dấu vết. Thay vào đó đánh
dấu và đưa ra màn hình.

**③ "Đang kẹt" là trạng thái riêng, không phải "chưa làm".** Một trụ chưa
tới lượt và một trụ dừng vì chờ cẩu trông giống hệt nhau nếu chỉ có
xong/chưa xong. Mà đó đúng là câu quản lý mở màn hình này để hỏi. Lý do
kẹt BẮT BUỘC khai.

**④ Trễ đo theo ngày kế hoạch của CHÍNH Ô ĐÓ**, không theo mốc hạng mục.
Hạng mục "móng 30 vị trí" xong đúng hạn vẫn có thể che một trụ trễ 40
ngày được bù bằng 29 trụ xong sớm.

Phần trăm hạng mục suy ngược, không gõ tay
-------------------------------------------
Mỗi cổng gắn với một hạng mục, nên hạng mục tính được **phần trăm vật
lý** từ số vị trí đã qua cổng — *13/30 móng xong* — thay vì nhận một con
số ai đó gõ vào. Số gõ tay không kiểm chứng được; số đếm từ 30 vị trí thì
có.

Và nó **không đè lên** ``progress_percent`` sẵn có. Trường cũ tính theo
*giá trị nghiệm thu đã duyệt / dự toán* — tiến độ **thanh toán**. Trường
mới đếm vị trí đã qua cổng — tiến độ **vật lý**. Hai số khác nhau là
bình thường, và **khoảng cách giữa chúng chính là thông tin**: việc đã
làm xong ngoài hiện trường mà chưa nghiệm thu được, tức chưa ra tiền.
Trộn hai cái làm một sẽ mất đúng khoảng cách đó.

Trên bản đồ
-----------
Bản đồ hiện trường thêm chế độ **tô màu theo tiến độ dựng máy** (đỏ 0% →
hổ phách → xanh 100%), bấm vào một trụ ra ngay *đang ở cổng nào, kẹt vì
gì, trễ mấy ngày*. Vị trí **chưa có sổ** để xám chứ không tô đỏ — chưa
khai khác với chưa làm, và tô đỏ sẽ biến một lỗ hổng dữ liệu thành báo
động giả.
""",
    'author': 'BSD Insight',
    'website': 'https://bsdinsight.com',
    'license': 'AGPL-3',
    'depends': ['eam_map', 'rp_cost_base', 'rp_progress', 'rp_estimate'],
    'data': [
        'security/ir.model.access.csv',
        'data/rp_erection_gate_data.xml',
        'views/rp_erection_views.xml',
    ],
    'installable': True,
}
