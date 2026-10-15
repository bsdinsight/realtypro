# -*- coding: utf-8 -*-
{
    'name': 'EAMOne — Phân công theo năng lực & chứng chỉ',
    'version': '19.0.1.0.0',
    'category': 'EAMOne',
    'summary': 'Chỉ giao việc cho người đủ chứng chỉ CÒN HIỆU LỰC vào '
               'ngày làm, và tách rõ thiếu hẳn với hết hạn.',
    'description': """
Phân công theo năng lực & chứng chỉ
===================================

Trong O&M điện gió, "đủ năng lực" hầu như không phải chuyện kỹ năng mà
là chuyện **giấy còn hiệu lực**: GWO, thẻ an toàn điện, tiếp cận bằng
dây, sơ cấp cứu — tất cả đều có thời hạn. Người vẫn làm được việc đó,
nhưng giấy hết hạn tháng trước thì không được lên trụ.

Dùng lại bảng kỹ năng của Odoo, KHÔNG dựng bảng riêng
------------------------------------------------------
``hr.employee.skill`` của Odoo 19 đã có ``valid_from``, ``valid_to`` và
cờ ``is_certification``. Dựng thêm một bảng chứng chỉ của EAMOne là có
**hai nguồn sự thật** về cùng một tờ giấy: phòng nhân sự cập nhật một
bên, đội bảo trì nhập một bên, rồi cổng chặn đọc bên nào cũng sai.

Module này chỉ tính thêm hai thứ Odoo không tính — tình trạng hiệu lực
và số ngày còn lại — rồi dùng chúng để chặn.

Kiểm theo NGÀY LÀM, không theo hôm nay
---------------------------------------
Đây là cái bẫy thật, và nó im lặng: hôm nay chứng chỉ còn hạn, lệnh xếp
làm ba tuần nữa, tới lúc làm thì đã quá hạn — mà cổng đã cho qua từ hôm
kiểm. Nên hiệu lực được soi tại **ngày dự kiến bắt đầu**, và khi lệnh
đã chạy thì tại ngày bắt đầu thật.

THIẾU HẲN và HẾT HẠN là hai bài toán khác nhau
-----------------------------------------------
Trên màn hình chúng giống nhau — cùng là "người này không được làm việc
đó" — nhưng khác nhau về thời gian xử lý:

* **Hết hạn** là lỗi xếp lịch đào tạo. Sửa được trong tuần: đăng ký lớp
  gia hạn, thi lại.
* **Thiếu hẳn** là lỗi kế hoạch nhân lực. Mất hàng tháng: tuyển, đào tạo
  từ đầu, hoặc thuê ngoài.

Gộp hai cái thành một câu "không đủ năng lực" là mất đúng thông tin cần
để xử lý. Nên mã này tách riêng, kể cả trong câu báo ở cổng chặn.

Chặn TRƯỚC khi làm, chỉ BÁO sau khi đã làm
-------------------------------------------
Cổng đặt ở lúc **bắt đầu** lệnh: đó là lúc chặn còn có tác dụng — đổi
người, đi gia hạn, hoặc hoãn một ngày.

Lúc **đóng** lệnh thì chỉ ghi nhận vào nhật ký, không chặn. Việc đã làm
rồi; chặn đóng lệnh vì người làm thiếu chứng chỉ không làm việc đó chưa
xảy ra — nó chỉ khiến người ta **sửa dòng giờ công cho khớp**, và thế là
mất luôn bản ghi thật về ai đã ở trên trụ. Thà có một lệnh đóng được kèm
nốt cảnh báo trong nhật ký, còn hơn một sổ giờ công đã bị gọt.

Phần ghi nhận này cũng soi cả người **không nằm trong tổ** mà vẫn có giờ
công — chỗ đó thường là nơi bắt đầu của một sự cố an toàn.

Mức siết mặc định là CẢNH BÁO
------------------------------
Bật chặn hẳn ngay trên một hệ đang chạy sẽ dừng công việc vốn hôm qua
vẫn làm bình thường, chỉ vì hồ sơ chứng chỉ chưa kịp nhập. Mặc định
``warn``; đổi tham số ``eam_competency.enforce`` sang ``block`` khi đã
nhập xong hồ sơ, hoặc ``off`` để tắt hẳn.

Khai năng lực ở KẾ HOẠCH, không khai lại ở từng lệnh
-----------------------------------------------------
Một kế hoạch bảo dưỡng sinh hàng chục lệnh mỗi năm trên hàng chục trụ.
Khai ở từng lệnh thì người tạo lệnh gấp sẽ bỏ trống — và cổng im lặng
cho qua đúng những lệnh gấp nhất.
""",
    'author': 'BSD Insight',
    'website': 'https://bsdinsight.com',
    'license': 'AGPL-3',
    'depends': ['eam_core', 'eam_work_order', 'eam_pm', 'hr_skills'],
    'data': [
        'data/eam_competency_data.xml',
        'views/eam_competency_views.xml',
    ],
    'installable': True,
}
