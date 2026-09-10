# Giấy phép — RealtyPro

Copyright © BSDInsight. Mọi quyền được bảo lưu theo các điều khoản dưới đây.

## 1. Giấy phép mở: AGPL-3.0

Phần mềm này được phát hành theo **GNU Affero General Public License
version 3** — toàn văn ở tệp [`LICENSE`](LICENSE), và một bản sao được
đặt trong thư mục của từng module.

Điều cần biết rõ nhất của AGPL, khác với GPL thông thường: **chạy phần
mềm đã sửa đổi thành dịch vụ qua mạng cũng là phát hành**. Ai vận hành
một bản phái sinh cho người khác dùng qua mạng thì phải cung cấp mã
nguồn của bản đó cho người dùng.

## 2. Vì sao TẤT CẢ module đều là AGPL-3

Trước đây một số module khai `LGPL-3`. Cách khai đó **không đúng thực
tế**: cả năm module LGPL đều phụ thuộc — trực tiếp hoặc bắc cầu — vào
module AGPL, nên tác phẩm kết hợp buộc phải theo AGPL. Nhãn LGPL tạo ra
kỳ vọng sai cho người nhận mã: rằng họ được ghép mã đóng vào mà không
phải công bố nguồn.

Không có module nào trong bộ này thực sự đứng độc lập khỏi phần nền
AGPL, nên gán cho đúng có nghĩa là **toàn bộ về AGPL-3**. Đây là ghi
đúng điều vốn đã đúng, không phải siết chặt thêm.

## 3. Giấy phép thương mại

BSDInsight là chủ sở hữu bản quyền của toàn bộ mã trong kho này, nên có
thể cấp **giấy phép thương mại riêng**, không kèm ràng buộc copyleft
của AGPL.

Giấy phép thương mại dành cho tổ chức muốn:

- phát hành sản phẩm phái sinh dưới dạng mã đóng;
- vận hành dịch vụ mạng dựa trên phần mềm này mà không công bố mã nguồn;
- ghép phần mềm này vào sản phẩm có giấy phép không tương thích với AGPL.

Liên hệ: **BSDInsight** — daibt@bsdinsight.com — https://bsdinsight.com

## 4. Đóng góp mã — đọc trước khi gửi

Mô hình hai giấy phép ở mục 3 **chỉ tồn tại được khi BSDInsight nắm
toàn bộ bản quyền**. Ngay khi có mã của người khác nằm trong kho mà
không kèm thoả thuận, BSDInsight mất khả năng cấp giấy phép thương mại
cho phần đó — và không sửa lại được nếu không xin được sự đồng ý của
từng người đóng góp.

Vì vậy, mọi đóng góp mã vào kho này cần kèm thoả thuận cho phép
BSDInsight phát hành phần đóng góp đó dưới **cả hai** giấy phép. Vui
lòng liên hệ trước khi gửi mã.

Với đối tác triển khai: cách làm được khuyến nghị là **không sửa vào
module của BSDInsight** mà viết module riêng dùng cơ chế kế thừa của
Odoo. Cách đó vừa tránh hẳn vấn đề bản quyền ở trên, vừa giúp hai bên
xác định được lỗi thuộc bên nào, vừa không bị ghi đè khi BSDInsight
phát hành bản mới.
