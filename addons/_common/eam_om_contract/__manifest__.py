# -*- coding: utf-8 -*-
{
    'name': 'EAMOne — Hợp đồng O&M & KPI/SLA',
    'version': '19.0.1.0.0',
    'category': 'EAMOne',
    'summary': 'Hợp đồng vận hành bảo dưỡng: phạm vi theo nhà máy, cam kết '
               'khả dụng, kỳ đánh giá theo hợp đồng, phí định kỳ và chế '
               'tài tính từ chính số đo được.',
    'description': """
EAMOne — Hợp đồng O&M & KPI/SLA
================================

Bảng RIÊNG, không dùng chung với hợp đồng EPC
----------------------------------------------
Hợp đồng EPC là một **hành trình một chiều có cổng chặn**: khởi công →
chạy thử → nghiệm thu → thời hạn khuyết tật → chứng chỉ thực hiện. Mỗi
cổng là nghĩa vụ một-lần, có ngày, đắt tiền nếu trượt.

Hợp đồng O&M là **dịch vụ lặp lại có đo đếm**: cùng một việc mỗi kỳ, và
cái quyết định tiền không phải mốc nào đã qua mà là **con số đo được
trong kỳ** có đạt cam kết hay không.

Nhét hai thứ đó vào một bảng thì quá nửa số cột phải để trống ở phân nửa
số dòng, và không ràng buộc nào còn đặt được — vì luật của bên này là
ngoại lệ của bên kia.

Ba chỗ dễ ra số đẹp mà sai
---------------------------

**① Mẫu số khả dụng là GIỜ-MÁY, không phải giờ đồng hồ.** Nhà máy điện
gió 30 tua-bin chạy một ngày có **720 giờ-máy**, không phải 24. Lấy tổng
giờ dừng của 30 máy chia cho 24 giờ thì khả dụng ra số âm; chia cho 720
mới đúng. Nên mẫu số **khai ra** ở ô *số đơn vị đo*, không để máy đoán —
đoán sai ở đây ra một con số vẫn nằm trong khoảng 0–100% nên không ai
nghi ngờ.

**② Cộng cả khoảng dừng cha lẫn con là đếm đúp.** Trạm nâng áp hỏng kéo
theo cả đội máy: sổ dừng máy ghi một khoảng "cha" ở trạm và nhiều khoảng
"con" ở từng máy. Phép đo ở đây **loại khoảng cha** ra, đúng như sổ dừng
máy đã dặn.

**③ Phạt khi còn nhiều giờ CHƯA QUY TRÁCH NHIỆM là phạt bằng số bịa.**
Khả dụng đối chiếu nhà thầu chỉ đếm khoảng dừng đã quy cho *nghĩa vụ hợp
đồng O&M*. Nếu trong kỳ còn một đống giờ ở trạng thái "chưa quy", con số
khả dụng trông vẫn đẹp — đẹp vì chưa ai phân loại, không phải vì nhà
thầu làm tốt. Nên mỗi dòng kết quả mang theo **số giờ chưa quy** và tự
cắm cờ khi nó đáng kể; người ký biên bản nhìn thấy trước khi ký.

Cam kết nào CHƯA đo được thì nói thẳng
---------------------------------------
Khả dụng theo **thời gian** đo được ngay hôm nay, từ sổ dừng máy. Khả
dụng theo **sản lượng** thì chưa: nó cần mô hình sản lượng đáng lẽ phát
được (đường cong công suất, máy đối chứng), thuộc module khác.

Khi hợp đồng cam kết theo cơ sở chưa đo được, dòng kết quả ghi **"chưa
đo được"** kèm lý do và **không tính phạt** — chứ không lặng lẽ thay
bằng cơ sở thời gian. Hai cơ sở ra hai con số khác nhau, và lấy nhầm là
tính tiền sai mà biên bản vẫn trông hoàn chỉnh.

Kỳ đánh giá theo HỢP ĐỒNG, không theo năm dương lịch
-----------------------------------------------------
Hợp đồng ký ngày 15/4 thì năm hợp đồng chạy 15/4 → 14/4, không phải 1/1
→ 31/12. Kỳ sinh ra từ ngày hiệu lực cộng chu kỳ, nên quý đầu có thể lẻ
ngày — đó là chuyện bình thường của hợp đồng, không phải lỗi.

Số đã chốt thì đóng băng
-------------------------
Kỳ đã chốt **chụp lại** mức cam kết, số đo được và phí tại thời điểm
chốt. Sửa cam kết hôm nay không được làm đổi biên bản kỳ trước — cùng
bài học đã trả giá ở hiệu suất điện mặt trời và ở đợt thanh toán bên
Realty CRM.
""",
    'author': 'BSD Insight',
    'website': 'https://bsdinsight.com',
    'license': 'LGPL-3',
    'depends': ['eam_core'],
    'data': [
        'security/ir.model.access.csv',
        'views/eam_om_contract_views.xml',
        'views/eam_om_period_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
