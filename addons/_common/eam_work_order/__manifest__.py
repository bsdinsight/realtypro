# -*- coding: utf-8 -*-
{
    'name': 'EAMOne — Lệnh công việc',
    'version': '19.0.1.0.0',
    'category': 'EAMOne',
    'summary': 'Chứng từ cho phép tiêu giờ công, vật tư và thời gian — '
               'kèm cổng an toàn và dữ liệu độ tin cậy.',
    'description': """
Lệnh công việc
==============

Maximo và ISO 14224 gọi *work order*; SAP PM gọi *maintenance order*.
Hai cái là một thứ. Tiếng Việt dùng **lệnh công việc**.

Đừng gọi là "lệnh công tác"
---------------------------
Trong ngành điện Việt Nam, **phiếu công tác** và **lệnh công tác** là hai
chứng từ AN TOÀN do quy chuẩn định nghĩa — mục 3.8 QCVN 25:2025/BCT (hiệu
lực 08/08/2025, thay QCVN 01:2020/BCT): giấy cho phép làm việc trên thiết
bị điện, do người có thẩm quyền cấp.

Lệnh công việc ở đây là chứng từ QUẢN LÝ BẢO TRÌ. Nó **trỏ tới** phiếu
công tác chứ không đóng vai phiếu đó, và có một cổng chặn: khai là cần
phiếu mà chưa có số hiệu thì không bấm bắt đầu được. Gộp hai thứ là vừa
làm hỏng hồ sơ an toàn vừa làm hỏng hồ sơ bảo trì.

Bốn quyết định thiết kế, cả bốn đều ngược trực giác
---------------------------------------------------

**① Dừng máy ≠ hỏng ≠ lệnh công việc.** Ba thực thể liên kết nhưng độc
lập. Rất nhiều lần dừng chỉ cần khởi động lại từ xa: có khoảng dừng,
không có hỏng, không có lệnh công việc. Bảo trì theo kế hoạch thì ngược
lại. Nên ``is_failure`` là ô KHAI TAY, không suy từ việc có lệnh hay
không — suy kiểu đó thì MTBF sai hoàn toàn, và sai theo hướng *đẹp hơn*
thực tế.

**② Người LÀM khác người TRẢ TIỀN.** Hãng chế tạo có thể tự cử người tới
sửa mà chủ đầu tư vẫn phải trả, vì đã hết bảo hành. Ngược lại tổ của chủ
đầu tư làm một việc mà chi phí đòi được từ nhà thầu O&M. ``executor`` và
``cost_bearer`` là HAI trường; gộp lại là mất dấu tiền đòi được.

**③ "Đang làm" lâu ngày thường là ĐANG CHỜ.** Một lệnh mở 14 ngày hiếm
khi có người làm suốt 14 ngày. Không ghi lý do chờ thì không phân biệt
được *sửa chậm* với *chờ một cái cẩu bánh xích phải huy động cả tuần*. Và
lý do chờ đúng là chỗ chế tài hợp đồng O&M cắn vào. Nên trạng thái vẫn là
"đang làm", còn việc chờ là một cờ riêng đo được — có màn hình **Lệnh đang
chờ** gom nhóm theo lý do, trả lời câu *tiền và thời gian đang mắc ở đâu*.

**④ Tổng chi phí thật = chi phí can thiệp + SẢN LƯỢNG MẤT.** Vật tư và
giờ công là phần nhìn thấy; với nhà máy điện thì phần lớn tiền nằm ở sản
lượng không phát được trong lúc máy dừng. Chỉ nhìn chi phí can thiệp thì
bảo trì phòng ngừa luôn trông như một khoản chi vô ích.

Ba tầng của hỏng hóc, đừng gộp
------------------------------
* **Dạng hỏng** — biểu hiện quan sát được: rò dầu, quá nhiệt, rung vượt
  ngưỡng.
* **Cơ chế hỏng** — quá trình vật lý dẫn tới: mỏi, mài mòn, ăn mòn.
* **Nguyên nhân gốc** — vì sao cơ chế đó xảy ra: lắp sai lực siết, bôi
  trơn thiếu, lỗi lô hàng.

Nhập cả ba vào một ô văn bản tự do thì vài năm sau không trả lời được câu
*"hộp số của đội máy này hỏng theo kiểu gì nhiều nhất"* — câu quyết định
nên siết bảo trì phòng ngừa ở đâu. Và cột *phát hiện bằng* trả lời câu
đắt tiền nhất: bao nhiêu phần trăm hỏng hóc được bắt TRƯỚC khi mất sản
lượng. Giám sát trạng thái chỉ đáng tiền khi tỷ lệ đó cao hơn hẳn.

Thay cấu phần quay vòng
-----------------------
Dòng vật tư có ``asset_out_id`` và ``asset_in_id``: thay một con hộp số là
THÁO con cũ ra và LẮP con mới vào, cả hai mang sê-ri riêng. Ghi mỗi số
lượng thì vài năm sau không biết trong máy đang có con nào — mà đó đúng là
câu cần trả lời khi đi đòi bảo hành.
""",
    'author': 'BSD Insight',
    'website': 'https://bsdinsight.com',
    'license': 'AGPL-3',
    'depends': ['eam_core', 'product'],
    'data': [
        'security/ir.model.access.csv',
        'data/eam_wo_sequence_data.xml',
        'views/eam_work_order_views.xml',
        'views/eam_outage_views.xml',
        'views/eam_wo_menus.xml',
    ],
    'installable': True,
}
