# -*- coding: utf-8 -*-
{
    'name': 'EAMOne — Tem QR / NFC hiện trường',
    'version': '19.0.1.0.0',
    'category': 'EAMOne',
    'summary': 'Quét tem ngoài hiện trường mở đúng thiết bị ĐANG lắp ở '
               'chỗ đó, không mở thiết bị đã bị tháo đi.',
    'description': """
Tem QR / NFC nhận diện thiết bị
===============================

Dán mã lên CHỖ, không dán lên THIẾT BỊ
---------------------------------------
Tem dán trên vỏ tháp là tem của **vị trí** (trụ T07), không phải của
thiết bị. Hộp số bên trong sẽ bị tháo ra đem về xưởng và thay bằng cái
khác; tua-bin vẫn là T07.

Hệ nào mã hoá *mã thiết bị* vào tem dán trên tháp thì sau hai năm luân
chuyển phụ tùng, **mọi tem ngoài hiện trường trỏ sai** — và sai một cách
im lặng: người thợ quét tem trên trụ T07, màn hình mở ra một hộp số đang
nằm trong kho, rồi họ ghi số đo của máy này vào hồ sơ của máy khác. Vài
tháng sau không ai dựng lại được dữ liệu đúng.

Nên tem vị trí **không trỏ tới thiết bị nào cả**: nó trỏ tới chỗ, và hệ
thống tra lịch sử lắp đặt để biết **hôm nay** chỗ đó đang là cái gì.
Thiết bị vẫn có tem riêng — dán lên chính nó, theo nó đi khắp nơi —
nhưng đó là tem khác, mang tiền tố khác.

Mã có tiền tố, và là chuỗi ngẫu nhiên
--------------------------------------
``L`` cho vị trí, ``A`` cho thiết bị. Tiền tố làm hai việc: người cầm
tem biết ngay đang cầm loại nào, và một mã gõ sai **không bao giờ mở ra
đúng một bản ghi khác loại** — nó báo lỗi.

Ngẫu nhiên thay vì số thứ tự, vì số thứ tự thì ai cũng dò được
``/eam/q/1`` tới ``/eam/q/9999`` để đếm nhà máy có bao nhiêu thiết bị.

Tem in kèm MÃ CHỮ
------------------
Tem ngoài trụ gió chịu nắng, mưa, bụi và dầu. QR xước một góc là máy
không đọc được nữa — nhưng người vẫn đọc được dòng chữ và tra tay. Tem
chỉ có QR là tem dùng được một năm.

Không giải được tem thì NÓI RÕ, không trả 404
----------------------------------------------
Người đang đứng dưới chân trụ với điện thoại cần biết nên làm gì tiếp,
không cần một mã lỗi HTTP. Trang thông báo nói thẳng: vị trí đang trống,
hoặc tem đã bị cấp lại mã — và **đừng ghi số đo vào một hồ sơ khác**.

Đổi mã là việc riêng, có xác nhận
----------------------------------
Hàm cấp mã cố ý **bỏ qua** bản ghi đã có mã: cấp lại hàng loạt là làm
chết mọi tem đã dán ngoài hiện trường. Muốn đổi thì có nút riêng, kèm
câu xác nhận nói rõ hệ quả.

NFC không cần thêm mã nguồn nào
--------------------------------
Thẻ NFC chỉ lưu một URL. Cùng đường dẫn ``/eam/q/<mã>`` này ghi vào thẻ
NFC là chạy y hệt — việc ghi thẻ làm bằng ứng dụng điện thoại, không
phải việc của phần mềm quản lý. Nên phần "NFC" của yêu cầu được đáp ứng
bằng chính cái đã có, và nói thẳng như vậy thì tốt hơn là dựng thêm một
module NFC cho đẹp danh mục.
""",
    'author': 'BSD Insight',
    'website': 'https://bsdinsight.com',
    'license': 'AGPL-3',
    'depends': ['eam_core', 'web'],
    'data': [
        'views/eam_qr_templates.xml',
        'report/eam_qr_label_report.xml',
        'views/eam_qr_views.xml',
    ],
    'installable': True,
}
