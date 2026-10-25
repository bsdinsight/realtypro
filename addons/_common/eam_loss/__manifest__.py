# -*- coding: utf-8 -*-
{
    'name': 'EAMOne — Hạch toán tổn thất',
    'version': '19.0.1.0.0',
    'summary': 'Lẽ ra phát được bao nhiêu, thực tế bấy nhiêu, phần chênh '
               'chia về từng nguyên nhân — và phần KHÔNG chia được.',
    'description': """
Hạch toán tổn thất — khung chung
=================================

Khác hẳn "tổn thất theo bậc" đã có trong chuỗi điểm đo. Hai câu hỏi
khác nhau:

* *Tổn thất theo bậc*: điện đi từ đầu ra máy tới công-tơ mất bao nhiêu.
  Đo được, cộng được, và luôn đúng vì cả hai đầu đều có số đo.
* *Hạch toán tổn thất*: LẼ RA phát được bao nhiêu, thực tế bấy nhiêu,
  phần chênh do đâu. Vế đầu không đo được — nó là một MÔ HÌNH, và mô
  hình nào cũng có phần không giải thích được.

Phần dư KHÔNG được phân bổ ngầm
--------------------------------

Biểu đồ thác nước cộng khít từ kỳ vọng xuống thực tế trông rất thuyết
phục, và đó chính là vấn đề: nó chỉ khít khi ai đó đã chia phần dư vào
các cột. Ở đây phần dư đứng riêng thành một cột có tên, và nó LỚN thì
tờ giấy nói ra rằng mô hình chưa giải thích được.

Hai mốc kỳ vọng, không phải một
--------------------------------

* **Mốc kế hoạch (P50)** — cam kết tài chính. Chênh với thực tế gồm cả
  phần tài nguyên: năm nay gió yếu hơn năm P50 thì sản lượng thấp mà
  chẳng ai làm gì sai.
* **Mốc tài nguyên** — đường cong công suất nhân gió ĐO ĐƯỢC. Chênh với
  thực tế mới là phần vận hành chịu trách nhiệm.

Gộp hai mốc làm một là đổ cho vận hành phần trời không cho.
""",
    'author': 'BSD Insight',
    'website': 'https://bsdinsight.com',
    'license': 'LGPL-3',
    'category': 'Industries/Energy',
    'depends': ['eam_core', 'eam_downtime', 'eam_chain', 'eam_unit_day',
                'eam_target', 'eam_historian', 'eam_availability'],
    'data': [
        'security/ir.model.access.csv',
        'data/eam_loss_type_data.xml',
        'views/eam_loss_views.xml',
    ],
    'installable': True,
    'application': False,
}
