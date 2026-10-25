# -*- coding: utf-8 -*-
{
    'name': 'EAMOne — Bảo hành thiết bị theo sê-ri',
    'version': '19.0.1.0.0',
    'category': 'EAMOne',
    'summary': 'Máy nào do ai cấp, theo hợp đồng nào, hết hạn bao giờ — '
               'một chỗ trả lời, kèm cảnh báo sắp hết đẩy ra người theo '
               'dõi.',
    'description': """
EAMOne — Bảo hành thiết bị theo sê-ri
======================================

Câu hỏi ba năm sau
-------------------
Hộp số hỏng. Câu đầu tiên luôn là: *con này do ai cấp, theo hợp đồng
nào, còn bảo hành không*. Trả lời được hay không quyết định **ai trả
tiền** cho lần sửa đó.

Thông tin ấy đã tồn tại trong hệ nhưng nằm rải: biên bản bàn giao từ
phần dự án mang nhà cung cấp và hợp đồng; lô hàng trong kho mang hạn bảo
hành tính từ ngày nhận. Rải ra thì mỗi lần hỏi lại phải đi lục, và máy
đến bằng đường khác thì không lục được ở đâu. Module này đưa câu trả lời
về **một chỗ — chính con máy** — và ghi luôn nó được kéo từ nguồn nào.

Nhà cung cấp KHÁC nhà sản xuất
-------------------------------
Sổ tài sản vốn đã có *nhà sản xuất* — ai **làm ra** con máy. Thiếu *nhà
cung cấp* — ai **cấp** nó. Bảo hành đòi ở bên cấp, không đòi ở bên làm,
nên thiếu ô này là thiếu đúng cái tên cần gọi.

Hai đồng hồ bảo hành, và luật phân xử
--------------------------------------
Một con phụ tùng quay vòng có hai hạn khác nhau về bản chất: trên **lô
hàng** tính từ ngày NHẬN (hàng nằm kho hai năm thì hết bảo hành trước
khi kịp lắp), trên **tài sản** là hạn khi đã vận hành. Cả hai đều đúng,
nhưng chỉ một cái trả lời được *lần sửa này ai trả tiền*.

Luật: lấy hạn trên **tài sản**, và khi hai hạn lệch nhau thì **cắm cờ**
chứ không tự chọn — lệch là dấu hiệu có người khai nhầm một trong hai,
và chọn hộ là giấu mất chuyện đó.

Lọc được mà vẫn không lưu con số sẽ cũ đi
------------------------------------------
``warranty_state`` là trường tính không lưu — đúng, vì "còn bao nhiêu
ngày" đổi theo từng ngày. Nhưng không lưu thì **không lọc được**: màn
"sắp hết bảo hành" không dựng nổi và cảnh báo không có gì để quét. Nên
bổ sung **hàm tìm kiếm** tự dựng điều kiện trên ngày hết hạn.

Tình trạng bảo hành trên phiếu được CHỤP LẠI
---------------------------------------------
Một phiếu gửi hàng đi sửa chỉ khác nhau một điều: lúc gửi, máy còn bảo
hành hay đã hết. Tình trạng ấy đổi theo ngày — phiếu lập hôm nay còn
hạn, ba tháng sau mở lại thì hệ tính ra "đã hết", và **biên bản tự lật
ngược kết luận của chính nó**. Nên nó được chụp lại lúc lập.

Và phiếu khai loại *bảo hành* trong khi máy đã hết hạn thì hệ **nói
ngay**: phiếu vẫn gửi đi được, nhưng bên kia sẽ từ chối, và cả quãng
chờ đó là thời gian chết.

Chưa ai theo dõi vẫn phải đếm
------------------------------
Cron bảy ngày một lần, không nhắc lại cùng một máy trong ba mươi ngày —
bảo hành hết dần suốt ba tháng, nhắc mỗi ngày thì chín mươi thông báo
cho một việc. Máy **chưa khai người theo dõi** vẫn được đếm và trả về,
chứ không bị bỏ qua trong im lặng: không có người nhận là một vấn đề
cần thấy, không phải lý do để thôi báo.
""",
    'author': 'BSD Insight',
    'website': 'https://bsdinsight.com',
    'license': 'LGPL-3',
    # Thêm eam_work_order: bảo hành không chỉ là một thuộc tính của con
    # máy, nó còn là một QUYẾT ĐỊNH trên lệnh sửa — "ai trả tiền lần
    # này". Màn "Còn bảo hành mà chưa đòi" nối hai thứ đó lại.
    'depends': ['eam_core', 'eam_stock', 'eam_work_order'],
    'data': [
        'data/eam_warranty_cron.xml',
        'views/eam_warranty_views.xml',
    ],
    'installable': True,
}
