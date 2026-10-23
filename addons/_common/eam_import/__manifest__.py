# -*- coding: utf-8 -*-
{
    'name': 'EAMOne — Nạp dữ liệu vận hành',
    'version': '19.0.1.0.0',
    'category': 'EAMOne',
    'summary': 'Khai một lần cách đọc tờ báo cáo ngày hoặc tệp xuất từ '
               'SCADA, rồi mỗi ngày chỉ còn tải tệp lên; có chạy thử '
               'trước khi ghi và nhật ký từng ô.',
    'description': """
EAMOne — Nạp dữ liệu vận hành
==============================

Vấn đề thật
-----------
Mọi con số của phần hiệu suất và phần chuỗi điểm đo hiện đều **nhập
tay**. Nhà máy thì đã có tệp: một tờ báo cáo vận hành ngày bằng Excel,
hoặc một tệp xuất từ hệ giám sát. Gõ lại tệp ấy vào phần mềm mỗi ngày là
việc không ai làm được lâu, và cũng là chỗ sai nhiều nhất.

Cách KHÔNG làm là viết một hàm đọc riêng cho tờ báo cáo của nhà máy đầu
tiên. Nhà máy thứ hai dùng mẫu khác — ô ở chỗ khác, tên bậc khác, đơn vị
khác — thế là viết hàm thứ hai; tới nhà máy thứ ba thì có ba đoạn mã gần
giống nhau và không ai dám sửa cái nào.

Ở đây **cách đọc tệp là dữ liệu**: khai một ``mẫu nạp`` nói rõ *ô nào đi
vào trường nào, nhân với bao nhiêu*. Một bộ mã đọc duy nhất chạy cho mọi
mẫu.

Hai hình dạng tệp, không phải một
----------------------------------
**Tờ biểu** — báo cáo vận hành ngày. Không phải bảng: nhãn nằm ở một
cột, số nằm ở một cột khác, và **cột chứa số thay đổi theo dòng** vì
vùng trộn của nhãn dài ngắn khác nhau. Trong tờ báo cáo thật đang dùng
để kiểm, khối khí tượng có giá trị ở cột P còn khối tổn thất ngay bên
dưới lại ở cột O — cùng một khối, cùng một cột nhãn. Nên địa chỉ phải
khai theo **từng ô**, không suy ra được bằng "giá trị luôn ở cột bên
phải".

**Bảng** — tệp xuất từ SCADA: một dòng tiêu đề, một cột thời điểm, mỗi
cột còn lại là một điểm đo.

Một tệp nuôi BA bảng cùng lúc
------------------------------
Tờ báo cáo ngày chứa khí tượng, hiệu suất và sản lượng của bảy bậc đo —
ba model khác nhau. Trình nhập sẵn có của Odoo đưa một tệp vào **một**
bảng, nên không dùng được. Và thứ tự ghi không tuỳ ý: tổng xạ với nhiệt
độ mô-đun trên bản ghi hiệu suất là trường *liên kết* lấy từ bản ghi khí
tượng, nên khí tượng phải vào trước. Trình nạp áp thứ tự **khí tượng →
hiệu suất → bậc đo → điểm đo** theo đích đến, không theo thứ tự dòng
người khai gõ vào — thứ tự đúng không nên phụ thuộc vào việc người khai
có biết luật đó hay không.

Chạy thử trước khi ghi
-----------------------
Một lượt nạp ghi vào ba bảng và bảy bậc. Ghi mù rồi mới xem là cách làm
hỏng im lặng cả tháng dữ liệu. Nên có **chạy thử**: đọc đủ, kiểm đủ, ra
đủ nhật ký — chỉ không ghi. Chạy thử và chạy thật dùng **đúng một đoạn
mã**, khác nhau một cờ; hai đoạn mã riêng thì sớm muộn chúng nói hai
chuyện khác nhau, và lúc đó chạy thử thành vô nghĩa.

Năm chỗ sai im lặng mà trình nạp này bắt
-----------------------------------------
**① Ô trỏ vào giữa vùng trộn.** Nhãn "Plant Irradiance" trộn từ L tới O,
giá trị nằm ở P. Khai nhầm ô O thì openpyxl trả về ``None`` — không lỗi,
không cảnh báo, trường chỉ đơn giản là rỗng. Nên mỗi ô đọc được kiểm xem
có nằm trong vùng trộn mà không phải góc trên trái hay không, và nhật ký
nói luôn giá trị thật nằm ở ô nào.

**② Đơn vị.** Tờ báo cáo ghi sản lượng bằng MWh, bảng của ta lưu kWh.
Thiếu hệ số 1000 thì 255 MWh thành 255 kWh — một phần nghìn, mà con số
vẫn là số dương trông hợp lý. Hệ số khai theo **từng dòng** (cùng một
khối có dòng MWh có dòng kWh), và nhật ký in **cả trị gốc lẫn trị đã
nhân** để người kiểm thấy phép nhân đã xảy ra.

**③ Hệ số bằng 0.** Để trống ô hệ số thì mọi giá trị thành 0 và không
báo gì. Ràng buộc chặn ở mức khai mẫu.

**④ Ngày trong ô ≠ ngày trên tên sheet.** Người trực nhân bản sheet hôm
qua rồi sửa số mà quên sửa ô ngày — toàn bộ số rơi vào ngày cũ, đè lên
dữ liệu đúng. Hai nguồn ngày được đối chiếu với nhau; lệch thì **dừng**,
vì ghi sai ngày tệ hơn không ghi.

**⑤ Đã nạp rồi.** Nạp lại cùng một ngày phải là chủ ý, không phải tai
nạn. Mặc định là từ chối kèm chỉ rõ ngày nào đã có; muốn đè thì bật cờ.

Tờ báo cáo tự kiểm công thức của ta
------------------------------------
Tờ báo cáo ngày không chỉ chứa đầu vào — nó chứa cả kết quả nhà máy tự
tính: PR, mẫu số, hệ số hiệu chỉnh nhiệt. Dòng khai được đánh dấu **chỉ
đối chiếu**: đọc lên, so với con số model ta tính ra, ghi khoảng lệch vào
nhật ký, **không ghi vào dữ liệu**.

Nghĩa là mỗi lần nạp một ngày, công thức của ta được kiểm lại bằng số
của chính nhà máy. Khoảng lệch mẫu số PR 2,53% hiện đang treo — thứ
trước đây phải dò bằng tay từng ngày — từ nay tự hiện ra ở mọi ngày nạp
vào, kèm biên độ.

Giới hạn nói thẳng
-------------------
* Đọc được ``.xlsx`` và ``.csv``. Báo cáo ngày của nhà máy điện gió hiện
  chỉ có bản **PDF** — chưa nạp được, cần bản Excel hoặc CSV.
* Chưa có bộ nối OPC-UA / Modbus đẩy số theo thời gian thực. Cổng nhận
  đã có sẵn ở kho chuỗi thời gian (``POST /eam/historian/nap``); phần
  còn thiếu là tiến trình ngoài gọi vào nó.
""",
    'author': 'BSD Insight',
    'website': 'https://bsdinsight.com',
    'license': 'LGPL-3',
    'depends': ['eam_core', 'eam_historian', 'eam_solar', 'eam_chain'],
    'data': [
        'security/ir.model.access.csv',
        'views/eam_import_views.xml',
        'data/eam_import_template_pv.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
