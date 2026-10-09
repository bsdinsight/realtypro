# -*- coding: utf-8 -*-
{
    'name': 'EAMOne — Bảo trì phòng ngừa',
    'version': '19.0.1.0.0',
    'category': 'EAMOne',
    'summary': 'Kế hoạch bảo trì theo lịch và theo giờ máy chạy, tự sinh '
               'lệnh công việc trước hạn.',
    'description': """
Bảo trì phòng ngừa
==================

Trước module này, EAMOne chỉ có lệnh công việc **phản ứng** — có sự cố
mới sinh lệnh. Một hệ quản lý bảo trì không có kế hoạch định kỳ thì chưa
phải hệ quản lý bảo trì, nó mới là sổ nhật ký sự cố.

Vòng khép kín:

::

    kế hoạch → lịch theo từng vị trí → cron sinh lệnh trước hạn
             → làm xong → ĐỒNG HỒ CHẠY TIẾP → chu kỳ sau

Năm chỗ các hệ CMMS hay làm sai
--------------------------------

**① Chu kỳ đếm từ lần LÀM XONG THẬT, không từ một lưới ngày cố định.**
Bảo dưỡng 6 tháng bị trễ 3 tuần thì lần sau cách lần vừa làm 6 tháng.
Giữ lưới cố định thì khoảng cách thật co lại còn 5 tháng, rồi có tháng
phải làm hai lần. Nhưng **kiểm định bắt buộc thì ngược lại**: hạn do
pháp luật đặt, làm sớm hay muộn thì hạn sau vẫn là ngày đó. Nên có hai
chế độ neo, và chọn sai chế độ là sai cả chuỗi về sau.

**② Hai điều kiện thì cái nào ĐẾN TRƯỚC thắng.** Thay dầu hộp số: *12
tháng hoặc 8.000 giờ chạy, tuỳ cái nào tới trước*. Hệ nào chỉ cho chọn
một trong hai là buộc người dùng bỏ đi một nửa điều kiện — và họ sẽ bỏ
cái khó đo, tức cái theo giờ, tức cái đúng hơn. Hai đơn vị khác nhau
không trừ trực tiếp được, nên so bằng **phần còn lại của chu kỳ**.

**③ Sinh lệnh TRƯỚC hạn một khoảng.** Sinh đúng ngày đến hạn là quá
muộn: chưa kịp đặt phụ tùng, chưa xếp được người, chưa thuê được cẩu.
Khoảng báo trước khai theo từng kế hoạch.

**④ Một kế hoạch × một vị trí chỉ có MỘT lệnh đang mở.** Cron chạy hằng
ngày, mà kế hoạch quá hạn thì ngày nào cũng thoả điều kiện — không chặn
thì sau một tháng có 30 lệnh y hệt nhau cho cùng một máy.

**⑤ Làm xong phải ĐẨY ĐỒNG HỒ CHẠY TIẾP.** Đây là chỗ dễ quên nhất:
không ghi lại ngày làm xong và số đồng hồ tại thời điểm đó thì chu kỳ
sau vẫn đếm từ lần trước nữa, kế hoạch lập tức quá hạn lại, cron sinh
lệnh mới, và người dùng thấy cùng một việc hiện ra mãi.

Đồng hồ đi lùi
--------------
Bảo trì theo giờ chạy là cách duy nhất đúng cho máy quay: một tua-bin ở
vùng gió mạnh chạy 3.500 giờ một năm, một con ở vùng lặng chạy 2.000 —
cùng "6 tháng" nhưng hao mòn khác hẳn.

Nhưng số đọc luỹ kế có một cái bẫy: **thay bộ điều khiển là bộ đếm về
0**. Cứ thế trừ thì ra một khoảng âm khổng lồ và mọi kế hoạch theo giờ
**tự lùi hạn vô thời hạn** — im lặng, không báo gì. Vài năm sau mới lộ
ra lúc hộp số hỏng trước kỳ thay dầu.

Nên số đọc thô giữ nguyên, và có một **giá trị liên tục** tính riêng
bằng cách cộng bù mỗi lần thay đồng hồ. Lần lùi nào **chưa được xác
nhận** là thay đồng hồ thì bị gắn cờ và **không cộng bù** — vì nó nhiều
khả năng là gõ nhầm.

Và kế hoạch chỉ chạy theo đồng hồ mà vị trí chưa có số đọc nào thì mang
trạng thái riêng **"thiếu số đọc"**, không phải "còn hạn". Nó sẽ im lặng
không bao giờ tới hạn, nên phải nói ra.
""",
    'author': 'BSD Insight',
    'website': 'https://bsdinsight.com',
    'license': 'AGPL-3',
    'depends': ['eam_core', 'eam_work_order'],
    'data': [
        'security/ir.model.access.csv',
        'data/eam_pm_cron.xml',
        'views/eam_pm_views.xml',
    ],
    'installable': True,
}
