# -*- coding: utf-8 -*-
{
    'name': 'Realty Project — Ranh giới & bàn giao giữa các gói thầu',
    'version': '19.0.1.0.0',
    'category': 'Realty/Project',
    'summary': 'Điểm bàn giao giữa hai nhà thầu: ai giao gì cho ai, bên '
               'nhận cần ngày nào, lịch hiện hành có kịp không.',
    'description': """
Realty Project — Sổ ranh giới (rp_interface)
============================================

Dự án lớn chia thành nhiều gói thầu, mỗi gói một nhà thầu. Chỗ hỏng
thường KHÔNG nằm trong hợp đồng nào cả — nó nằm ở **điểm bàn giao** giữa hai
hợp đồng: nhà thầu móng phải bàn giao mặt bằng và bu-lông neo đúng cao
độ cho nhà thầu lắp dựng; hãng thiết bị phải giao bản vẽ tải trọng cho
bên thiết kế móng; bên vận chuyển phải giao thiết bị tại bãi cho bên cẩu
lắp. Hợp đồng nào cũng báo "đúng tiến độ của tôi" mà dự án vẫn trễ, là
vì không ai giữ sổ này.

Mỗi điểm bàn giao ghi: bên giao, bên nhận, thứ được bàn giao, điều kiện
nghiệm thu, người phụ trách hai bên, ngày bên nhận CẦN và ngày bên giao
HỨA.

Điểm khác với một bảng Excel:

* **Đối chiếu thẳng với lịch thi công.** Mỗi điểm bàn giao nối tới việc tạo
  ra (bên giao) và việc chờ (bên nhận); hệ thống lấy ngày từ lịch hiện
  hành và tính dư địa. Dư địa ÂM = lịch đang mâu thuẫn, bên nhận phải
  chờ — thấy trước khi ra công trường.
* **Nối vào lịch một nút bấm**: khai việc bên giao là công việc trước
  của việc bên nhận, để đường găng toàn dự án chạy xuyên qua điểm bàn giao.
* **Quét sổ từ lịch có sẵn**: mọi quan hệ trước-sau nối hai hợp đồng
  khác nhau đều là điểm bàn giao có thật, chỉ là chưa ai ghi. Quét một lượt
  là có sổ, rồi bổ sung điều kiện nghiệm thu và người phụ trách.
""",
    'author': 'BSDInsight',
    'website': 'https://bsdinsight.com',
    'license': 'LGPL-3',
    'depends': [
        'rp_contract',
        'rp_schedule',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_sequence.xml',
        'views/rp_interface_views.xml',
        'views/re_project_views.xml',
        'views/rp_contract_views.xml',
        'views/rp_interface_menus.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
