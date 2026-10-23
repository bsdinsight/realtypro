# -*- coding: utf-8 -*-
{
    'name': 'EAMOne — Khả dụng & kỳ hợp đồng',
    'version': '19.0.1.0.0',
    'category': 'EAMOne',
    'summary': 'Khả dụng theo sản lượng bên cạnh khả dụng theo thời gian; '
               'luỹ kế ngày/tháng/năm cộng đúng cách; nối thẳng vào cam '
               'kết hợp đồng O&M.',
    'description': """
EAMOne — Khả dụng & kỳ hợp đồng
================================

Hai con số, hai câu hỏi khác nhau
----------------------------------
Khả dụng theo **thời gian** hỏi *bao nhiêu phần trăm thời gian nhà máy
sẵn sàng*. Khả dụng theo **sản lượng** hỏi *bao nhiêu phần trăm điện lẽ
ra phát được đã thật sự phát*.

Một tua-bin dừng một ngày giữa mùa lặng gió mất gần như không gì; dừng
một ngày giữa mùa gió mạnh mất cả chục nghìn kWh. Khả dụng theo thời
gian trừ **cùng một lượng** cho cả hai. Đó là lý do hợp đồng dịch vụ dài
hạn của hãng thường cam kết theo sản lượng: nó là thứ ra tiền.

Mẫu số không phải con số lý thuyết
-----------------------------------
``sản lượng đáng lẽ = sản lượng thực + sản lượng mất``. Mẫu số dựng từ
thực tế cộng phần mất **đã hạch toán từng dòng**, nên nhà thầu cãi được
từng lần dừng thay vì cãi một con số từ trên trời.

Phần mất lấy từ **đúng engine của sổ giờ dừng máy**, không tính lại.

LUỸ KẾ KHÔNG PHẢI TRUNG BÌNH CÁC NGÀY
--------------------------------------
Đây là chỗ sai im lặng nhất của mọi báo cáo khả dụng. Trung bình cộng
phần trăm của ba mươi ngày cho mỗi ngày một trọng số bằng nhau, trong
khi ngày lặng gió và ngày gió mạnh đóng góp sản lượng khác nhau cả chục
lần. Đúng là **cộng tử số rồi chia tổng mẫu số**. Hai cách ra hai con
số, và cách sai **luôn đẹp hơn** vì ngày xấu bị pha loãng.

Công suất khả dĩ — cách thứ hai để suy phần mất
------------------------------------------------
Sổ giờ dừng máy đã có cách **máy đối chứng**. Cách đó chịu thua đúng lúc
cần nhất: bão làm cả nhà máy dừng thì không còn ai làm đối chứng. Cách
ở đây không cần máy nào chạy — lấy điều kiện tự nhiên đo được trong
chính khoảng đó::

    điện gió      tốc độ gió → đường cong công suất đã nghiệm thu
    điện mặt trời bức xạ     → diện tích × hiệu suất mô-đun

Vẫn giữ **cả hai** vì chúng khác nhau có hệ thống: đường cong là cam kết
của hãng trong điều kiện chuẩn, còn máy thật sau vài năm không chạy đúng
đường cong đó nữa. Dùng đường cong thì phần mất luôn hơi cao, có lợi cho
bên đi đòi. Hợp đồng quy định dùng cách nào, nên ở đây **khai được**.

Gió lấy bước mười phút chứ không trung bình cả khoảng: quan hệ giữa tốc
độ gió và công suất là bậc ba, nên trung bình trước rồi tra sau ra số
thấp hơn hẳn tổng của từng bước.

Bịt lỗ hổng mà hợp đồng tự khai
--------------------------------
Phần hợp đồng O&M khai thẳng rằng cam kết "khả dụng theo sản lượng"
**chưa đo được**, và mỗi kỳ ra một dòng nói rõ như vậy. Module này kế
thừa đúng hai phương thức phần đó đã chừa sẵn để làm nó đo được — không
dựng engine thứ hai. Nhờ vậy mọi thứ đã có quanh hợp đồng (chụp số lúc
chốt kỳ, làm tròn trước khi tính phạt, chặn trần, cảnh báo giờ chưa quy)
chạy nguyên vẹn cho cơ sở mới mà không sửa một dòng nào bên đó.
""",
    'author': 'BSD Insight',
    'website': 'https://bsdinsight.com',
    'license': 'LGPL-3',
    'depends': ['eam_downtime', 'eam_om_contract', 'eam_chain'],
    'data': [
        'security/ir.model.access.csv',
        'views/eam_availability_views.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
}
