# -*- coding: utf-8 -*-
{
    'name': 'EPCOne — Cảnh báo trượt tiến độ',
    'version': '19.0.2.0.0',
    'category': 'Realty/Project',
    'summary': 'Quét hằng ngày: việc hết dư địa, việc trượt kế hoạch gốc, '
               'điểm bàn giao mâu thuẫn, dự án trễ mốc — có lịch sử, tự đóng.',
    'description': """
EPCOne — Cảnh báo trượt tiến độ (rp_schedule_alert)
===========================================================

Lịch thi công và sổ ranh giới gói thầu đã đủ số để biết dự án hỏng ở đâu, nhưng
chỉ khi có người MỞ RA XEM. Không ai soi 485 công việc mỗi sáng, nên
chuyện trượt thường lộ ra lúc đã muộn.

Mỗi sáng hệ thống quét bốn ngưỡng (chỉnh theo từng dự án):

* **Cả dự án trễ mốc phải xong** — ngày về đích dự báo vượt COD / ngày
  bàn giao cam kết.
* **Công việc hết dư địa** trên đường găng toàn dự án.
* **Công việc trượt so kế hoạch gốc** quá ngưỡng mà chưa xong.
* **Điểm bàn giao mâu thuẫn** — bên nhận cần trước khi bên giao kịp xong.

Ba điều quyết định việc này dùng được hay không:

* **Không nhân bản**: cùng một chuyện thì cập nhật con số, không tạo
  thêm bản ghi — nhờ vậy mới trả lời được "cảnh báo từ bao giờ", bằng
  chứng cho hồ sơ khiếu nại.
* **Tự đóng** khi điều kiện hết, có ghi ngày. Danh sách luôn là tình
  trạng hiện tại, không phải bãi rác.
* **Một bản tin mỗi lần quét** vào nhật ký dự án, thay vì bắn hàng chục
  thông báo — bắn nhiều thì người ta tắt, và cảnh báo thật chết theo.
""",
    'author': 'BSDInsight',
    'website': 'https://bsdinsight.com',
    'license': 'LGPL-3',
    'depends': [
        'rp_schedule',
        'rp_interface',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_cron_data.xml',
        'views/rp_schedule_alert_views.xml',
        'views/re_project_views.xml',
        'views/rp_schedule_alert_menus.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
