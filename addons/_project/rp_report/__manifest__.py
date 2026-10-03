# -*- coding: utf-8 -*-
{
    'name': 'Realty Project — Báo cáo theo vai',
    'version': '19.0.1.0.0',
    'category': 'Realty/Project',
    'summary': 'Mỗi phòng ban một màn hình đã lọc sẵn, cộng bản tổng hợp '
               'dự án chốt theo kỳ để so sánh giữa các kỳ.',
    'description': """
Realty Project — Báo cáo theo vai (rp_report)
=============================================

Dữ liệu đã có đủ ở các module nghiệp vụ, nhưng mỗi phòng ban lại cần một
lát cắt khác nhau. Nếu ai cũng tự đi lọc thì mỗi người ra một con số và
cuộc họp biến thành tranh luận về số liệu.

**Menu Báo cáo chia theo PHÒNG BAN, không chia theo bảng dữ liệu:**

* **Lãnh đạo** — bản tổng hợp dự án, cảnh báo nghiêm trọng.
* **Ban quản lý dự án** — công việc đang trượt (nhóm theo hợp đồng),
  công việc trên đường găng, điểm giao mâu thuẫn, cảnh báo đang mở.
* **Tài chính** — hợp đồng kèm giá gốc / phát sinh đã duyệt / phát sinh
  đang chờ / dự báo / gia hạn / ngày chậm / phạt dự kiến trên MỘT dòng;
  phát sinh dạng pivot theo trạng thái; danh sách hợp đồng đang chậm.
* **Mua sắm & pháp chế** — phát sinh đang xử lý, khiếu nại đang mở.

Mọi màn hình đều là dữ liệu gốc của các module nghiệp vụ, chỉ đổi lát
cắt — không nhân bản số liệu — và xuất Excel được ngay bằng chức năng
sẵn có của Odoo.

**Bản tổng hợp dự án (rp.project.brief)** chốt ~25 chỉ số của một dự án
tại một thời điểm: tiến độ, phối hợp, tiền, hợp đồng. Số được CHỤP LẠI
chứ không tính động — báo cáo tháng 10 phải giữ nguyên con số tháng 10
kể cả khi lịch đổi vào tháng 11. Nhờ vậy mới so sánh được giữa các kỳ,
là thứ báo cáo quản trị cần. Cron chốt số đầu mỗi tháng; trước họp giao
ban thì bấm nút chốt tay.
""",
    'author': 'BSDInsight',
    'website': 'https://bsdinsight.com',
    'license': 'LGPL-3',
    'depends': [
        'rp_schedule',
        'rp_interface',
        'rp_schedule_alert',
        'rp_claim',
        'rp_variation',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_cron_data.xml',
        'views/rp_project_brief_views.xml',
        'views/rp_report_actions.xml',
        'views/re_project_views.xml',
        'views/rp_report_menus.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
