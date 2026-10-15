# -*- coding: utf-8 -*-
{
    'name': 'EAMOne — Bảo trì phòng ngừa',
    'version': '19.0.1.2.0',
    'category': 'EAMOne',
    'summary': 'Kế hoạch bảo trì theo lịch và theo giờ máy chạy, tự sinh '
               'lệnh công việc trước hạn, có luật theo mùa và KPI độ tin '
               'cậy.',
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

Lịch theo mùa: kéo lên sớm, KHÔNG đẩy lùi
------------------------------------------
Mùa là **cửa sổ lặp hằng năm** (chỉ khai ngày-tháng), và chạy được cả
với mùa vắt qua năm mới — mùa gió mạnh tháng 11 tới tháng 3 là một mùa,
không phải hai.

Đây là chỗ các hệ lập lịch theo mùa làm sai, và sai theo hướng nguy
hiểm. Hạn thay dầu hộp số rơi vào giữa mùa mưa, không leo trụ được. Lối
xử lý tự nhiên của phần mềm là **đẩy sang sau mùa mưa** — và thế là hộp
số chạy thêm bốn tháng quá kỳ thay dầu, *xuyên qua đúng mùa khắc nghiệt
nhất*. Đúng phải là **kéo lên trước khi mùa bắt đầu**: với bảo trì phòng
ngừa, làm sớm là an toàn, làm muộn là rủi ro — hai hướng không đối xứng.

Nên thuật toán dời **ít nhất có thể**, và trong các ngày dời bằng nhau
thì chọn ngày **sớm**. Phải đẩy lùi thì vẫn làm được, nhưng luôn kèm câu
nói rõ thiết bị sẽ chạy thêm bao nhiêu ngày quá chu kỳ thiết kế.

Bốn chốt nữa:

* **Kiểm định bắt buộc KHÔNG bao giờ bị dời.** Hạn do pháp luật đặt;
  quá hạn là phải dừng thiết bị, không phải chỉ số xấu đi. Nó được *báo
  xung đột mùa* để đi chuẩn bị điều kiện khác, chứ không được hoãn.
* **"Nên làm trong mùa này" không gây dời ngày.** Cho nó quyền đó thì hệ
  thống sẽ sẵn sàng đẩy việc lùi ba tuần để rơi vào mùa khô — đúng hướng
  nguy hiểm. Nó chỉ dùng để chọn giữa những ngày đã bằng điểm.
* **Hạn gốc không bị ghi đè.** Ngày đề xuất là một cột riêng; chênh lệch
  giữa hai cột chính là thứ cần nhìn. Ghi đè thì sau vài lần dời không ai
  biết thiết bị đã trễ bao lâu so với chu kỳ thiết kế.
* **Việc bị kéo lên sớm được sinh lệnh sớm hơn tương ứng.** Bỏ chốt này
  thì tới lúc cron thấy hạn gốc tới gần, ngày đề xuất đã trôi qua từ
  lâu — và cả tính năng chỉ còn là một dòng ghi chú.

Luật mùa khớp theo **nghề**, không chỉ theo loại việc. Đó là chỗ nó đáng
tiền nhất: mùa mưa thì *tiếp cận bằng dây* không làm được, nhưng việc
trong tháp vẫn làm bình thường.

Độ tin cậy & KPI bảo trì
-------------------------
MTBF chia cho **giờ máy chạy** đọc từ đồng hồ, không chia giờ lịch —
tua-bin dừng vì lặng gió không phải thời gian "đang chạy mà không hỏng".
MTTR **loại** giờ chờ, MDT giữ nguyên toàn bộ: khoảng cách giữa hai số
chính là chi phí hậu cần. Mỗi dòng lưu **cả tử số lẫn mẫu số**, và thiếu
bằng chứng thì để trống kèm lý do chứ không để 0 — "MTTR = 0" đọc như
sửa tức thì.
""",
    'author': 'BSD Insight',
    'website': 'https://bsdinsight.com',
    'license': 'AGPL-3',
    'depends': ['eam_core', 'eam_work_order'],
    'data': [
        'security/ir.model.access.csv',
        'data/eam_pm_cron.xml',
        'views/eam_pm_views.xml',
        'views/eam_season_views.xml',
        'views/eam_reliability_views.xml',
    ],
    'installable': True,
}
