# -*- coding: utf-8 -*-
{
    'name': 'EAMOne — Cảnh báo tự sinh lệnh',
    'version': '19.0.1.1.0',
    'category': 'EAMOne',
    'summary': 'Sổ cảnh báo bất khả tri về nguồn, tự mở lệnh công việc, '
               'và đếm số lần tái phát sau sửa.',
    'description': """
Cảnh báo → lệnh công việc
=========================

Giám sát mà không nối sang việc làm thì chỉ để ngắm. Module này là cây
cầu: **bất thường → cảnh báo → lệnh công việc → sửa → khép cảnh báo**,
và vòng đó phải khép ở cả hai đầu.

Vì sao sổ cảnh báo KHÔNG gắn vào một hệ giám sát cụ thể
-------------------------------------------------------
Hôm nay chưa có bộ kết nối SCADA/OPC. Hàn sổ cảnh báo vào một driver
chưa tồn tại thì cả chuỗi phải chờ driver, mà driver thì chờ dự án. Nên
sổ này **bất khả tri về nguồn**: nó chạy được ngay hôm nay bằng đồng hồ
đang có và bằng người trực, nhận được cảnh báo hệ ngoài đẩy vào qua API,
và khi SCADA về thì đó chỉ là thêm một nguồn nữa — không phải viết lại.

Ba nguồn tự động, và chỗ hay bị lẫn
------------------------------------
``Ngưỡng đồng hồ`` — số đồng hồ vượt mức. Dùng cho đồng hồ **trạng
thái** (độ rung, nhiệt độ dầu). Đặt ngưỡng lên *giờ máy chạy* là trùng
việc với kế hoạch bảo trì phòng ngừa, rồi hai cơ chế cùng sinh lệnh cho
một việc — màn hình cấu hình có dải cảnh báo đúng chỗ đó.

``Mất số đọc`` và ``Đồng hồ đứng im`` **khác nhau, và lẫn hai cái này
là lỗi kinh điển**:

* **Mất số đọc** — không có số đọc mới trong N ngày. *Đường truyền*
  chết, không phải máy chết. Việc phải làm là gọi người IT.
* **Đồng hồ đứng im** — số đọc vẫn về đều nhưng giờ chạy **không tăng**.
  Máy đứng im thật. Việc phải làm là ra hiện trường.

Hệ nào gộp hai cái thành một "mất tín hiệu" thì đội vận hành chạy nhầm
hướng: cử người leo trụ vì tưởng máy dừng trong khi chỉ đứt cáp mạng —
hoặc tệ hơn, bỏ qua một trụ đứng im cả tuần vì số đọc vẫn về đều đặn.

Ba chỗ chống rác
----------------
**① Một bản ghi là một ĐỢT, không phải một lần nổ.** Cron chạy hằng
ngày mà điều kiện còn đúng thì ngày nào cũng thoả — ghi một dòng mỗi
ngày là sau một tháng có 30 cảnh báo y hệt nhau cho cùng một trụ. Nổ lại
trong đợt chỉ cộng ``số lần nổ``. Và chính con số đó lại là thông tin:
*"đã nổ 47 lần"* nói khác hẳn *"vừa nổ"*, dù hai dòng trông giống nhau.

**② Mặc định KHÔNG tạo lệnh ngay.** Một đầu đo rung bị nhiễu có thể nổ
500 cảnh báo một đêm. Tạo lệnh ngay thì sáng ra danh sách lệnh có 500
dòng rác — và cái hỏng thật nằm ở đó vẫn không ai thấy. Thất bại nguy
hiểm của tự động hoá ở đây không phải *bỏ sót một cảnh báo*, mà là **làm
cho danh sách lệnh mất giá trị**, sau đó thì bỏ sót tất cả. Nên mặc định
là *tạo sau khi người trực xác nhận*; riêng mức nghiêm trọng thì tạo
ngay, vì ở đó chờ xác nhận đắt hơn chịu rác.

**③ Nhiều cảnh báo cùng một trụ gộp về MỘT lệnh.** Ba luật khác nhau
cùng nổ ở một tua-bin vẫn chỉ cần một lần đi hiện trường.

``Số lần tái phát sau sửa`` — con số đắt nhất
----------------------------------------------
Cảnh báo tắt vì đã đóng lệnh sửa, rồi quay lại sau hai tuần. Nghĩa là
**lần sửa đó không giữ được**: sửa sai chỗ, hoặc chỉ xử lý triệu chứng,
hoặc phụ tùng thay vào là phụ tùng kém.

Không hệ CMMS nào theo dõi con số này, và mọi đội bảo trì đều cần nó —
vì nó là cách duy nhất phân biệt **"đã sửa"** với **"đã đóng lệnh"**.
Đợt tái phát còn được nâng một mức nghiêm trọng so với luật: thứ quay
lại sau khi đã sửa thì nguy hơn lần đầu, không phải bằng.

Và im lặng đủ lâu rồi mới nổ lại thì **không** tính là tái phát. Đếm
bừa là thổi phồng đúng con số đáng tin nhất của sổ này.

Hai chỗ cố ý không tự động
---------------------------
* **Đợt đã có lệnh thì không tự tắt.** Trị số về bình thường trong lúc
  chờ sửa là chuyện thường (máy được cho dừng) — tắt đi là để lại một
  lệnh mồ côi không ai biết mở ra vì sao.
* **Cờ "lệnh xong thì xoá cảnh báo" tắt được.** Dùng cho cảnh báo phải
  tự hết bằng số đo trở lại bình thường: sửa xong mà độ rung vẫn cao thì
  chưa sửa được, và tuyên bố "đã hết" vì có người bấm đóng lệnh là nói
  sai.

Bỏ qua phải khai lý do
----------------------
Bỏ qua là lối thoát mà ai cũng dùng khi cảnh báo nhiều quá. Không bắt
khai lý do thì sau sáu tháng sổ này đầy dòng "đã bỏ qua" mà không ai nhớ
vì sao, kể cả người bỏ qua.
""",
    'author': 'BSD Insight',
    'website': 'https://bsdinsight.com',
    'license': 'AGPL-3',
    # Phụ thuộc eam_pm vì đồng hồ thiết bị (eam.meter) nằm ở đó — và hôm
    # nay đồng hồ là nguồn cảnh báo tự động duy nhất thực sự có dữ liệu.
    'depends': ['eam_core', 'eam_work_order', 'eam_pm'],
    'data': [
        'security/ir.model.access.csv',
        'data/eam_alarm_cron.xml',
        'views/eam_alarm_rule_views.xml',
        'views/eam_alarm_views.xml',
        'views/eam_work_order_views.xml',
        'views/eam_alarm_menus.xml',
    ],
    'installable': True,
}
