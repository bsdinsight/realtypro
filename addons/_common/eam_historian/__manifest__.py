# -*- coding: utf-8 -*-
{
    'name': 'EAMOne — Kho chuỗi thời gian (Historian)',
    'version': '19.0.1.1.0',
    'category': 'EAMOne',
    'summary': 'Lưu số đo tần suất giây–phút cho toàn bộ điểm đo, ngoài '
               'ORM, có làm sạch dữ liệu và tag tính toán.',
    'description': """
Kho chuỗi thời gian
===================

Tách đôi dứt khoát
------------------
**Siêu dữ liệu** (điểm đo là gì, đơn vị gì, gộp thế nào, thế nào là số
vô lý) nằm ở model Odoo ``eam.tag``. **Số đo** nằm ở bảng
``eam_tag_reading`` do module tự tạo và tự quản bằng SQL thuần, KHÔNG
đi qua ORM.

Lý do là quy mô: một nhà máy 12 tua-bin, 50 điểm đo mỗi trụ, lấy mẫu 1
giây là 600 dòng mỗi giây — 52 triệu dòng một ngày, 19 tỷ dòng một
năm. Với nhịp 1 phút vẫn là 315 triệu dòng một năm. ORM không dành cho
việc đó, và không phải vì chậm một chút: ``create()`` chạy hàm tính,
ghi nhật ký và kiểm quyền từng dòng; còn một bảng ``ir.model`` vài tỷ
dòng làm hỏng chính công cụ của Odoo, vì màn danh sách sẽ cố đếm tổng
số dòng và câu đếm đó không bao giờ xong.

PostgreSQL thuần, không TimescaleDB
------------------------------------
Máy chủ chạy ``postgres:16`` không có TimescaleDB, và container cơ sở
dữ liệu đó đang phục vụ **bốn** cơ sở dữ liệu sống. Đổi image để lấy
một extension là rủi ro không tương xứng ở quy mô hiện tại.

Nên kho dùng **phân mảnh theo tháng** của PostgreSQL 16, cộng chỉ mục
BRIN trên trục thời gian (dữ liệu chèn gần như theo thứ tự thời gian
nên BRIN nhỏ hơn btree hàng trăm lần mà vẫn cắt được khoảng).

Mọi chỗ phụ thuộc công nghệ gom vào đúng một file, nên lắp TimescaleDB
sau này là thay phần tạo bảng và thêm chính sách nén, không đụng phần
còn lại. Nói thẳng giới hạn: **nhịp 1 giây cho cả nhà máy thì cần
nén**, tức cần TimescaleDB hoặc tương đương.

Gộp sai là chỗ sai IM LẶNG nhất
--------------------------------
Mỗi điểm đo khai cách gộp riêng, vì gộp nhầm vẫn ra con số trông hợp lý:

* Công suất (kW) gộp bằng **trung bình** — đúng.
* Điện năng luỹ kế (kWh) gộp bằng trung bình ra số vô nghĩa; phải lấy
  **hiệu đầu–cuối**. Hiệu âm nghĩa là đồng hồ đã thay hoặc quay vòng —
  trả **NULL** chứ không trả số âm, cũng không kẹp về 0: cả hai đều là
  bịa ra một con số không ai kiểm được.
* Trạng thái 0/1 phải lấy **giá trị cuối**.
* **Hướng gió không gộp số học được.** Trung bình của 350° và 10° ra
  180° — ngược hẳn hướng thật. Phải lấy trung bình VECTƠ. Bỏ qua chuyện
  này thì hoa gió sai hoàn toàn mà biểu đồ vẫn mượt.

Làm sạch dữ liệu: ĐÓNG CỜ, không xoá
-------------------------------------
Ba luật — ngoài dải hợp lý, biến thiên quá nhanh, và **kẹt** (đầu đo
chết thường trả đúng một giá trị mãi, và giá trị đó nằm trong dải hợp
lý nên kiểm dải không bắt được). Cả ba chỉ gắn **cờ chất lượng** dạng
bitmask; số thô giữ nguyên vĩnh viễn. Lọc xong xoá bản gốc thì không
bao giờ chứng minh lại được, mà yêu cầu lưu trữ nói rõ *không xoá,
không nén mất mát dữ liệu gốc*.

Người đọc tự chọn có lọc theo cờ hay không. Mặc định là **không lọc**:
phải thấy dữ liệu thật trước, lọc sẵn thì không ai biết đã bỏ bao nhiêu.

Tag tính toán
-------------
Công thức viết bằng mã tag, tính **lúc đọc** chứ không lưu sẵn. Sửa
công thức là mọi biểu đồ cũ cũng đổi theo — đó là điều mong muốn: công
thức sai phải sai ở mọi chỗ, chứ không để lại số cũ tính bằng công thức
cũ mà không ai biết là đã khác.

Khoảng nào thiếu một tag nguồn thì **bỏ**, không thay bằng 0: số 0 ở
mẫu ra vô cực, ở tử ra một hiệu suất bằng 0 trông như sự cố thật.

Cổng nạp bất khả tri về nguồn
------------------------------
``POST /eam/historian/nap`` nhận lô số đo từ bất cứ thứ gì đẩy được
HTTP: script đọc Modbus, gateway OPC-UA, tệp CSV của hãng, hay bộ kết
nối SCADA khi nó về. Gửi lại là **vô hại** (``ON CONFLICT DO UPDATE``)
vì phát lại một khoảng sau khi mất kết nối là chuyện bình thường.

Lô hỏng một dòng thì **không hỏng cả lô**: dòng nào nhận được thì nhận,
dòng nào không thì báo lại kèm chỉ số dòng và lý do. Hỏng cả lô vì một
dòng thì bộ kết nối sẽ thử lại mãi cùng lô đó và dữ liệu phía sau dồn
lại vô hạn.
""",
    'author': 'BSD Insight',
    'website': 'https://bsdinsight.com',
    'license': 'AGPL-3',
    'depends': ['eam_core'],
    'data': [
        'security/ir.model.access.csv',
        'data/eam_historian_cron.xml',
        'views/eam_tag_views.xml',
        'views/eam_exclusion_views.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
}
