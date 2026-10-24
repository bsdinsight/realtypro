# -*- coding: utf-8 -*-
{
    'name': 'EAMOne — Mục tiêu sản lượng P50 / P75 / P90',
    'version': '19.0.1.0.0',
    'category': 'EAMOne',
    'summary': 'Mục tiêu theo nhà máy × tháng ở BA mức xác suất — một '
               'bảng dùng chung cho tờ báo cáo ngày và phần phân tích.',
    'description': """
EAMOne — Mục tiêu sản lượng P50 / P75 / P90
============================================

Ba mức, không phải một
-----------------------
Sản lượng một nhà máy gió hay mặt trời không phải con số, mà là một
**phân phối**: gió năm nay mạnh hơn năm ngoái thì sản lượng khác, và
không ai điều khiển được chuyện đó.

* **P50** — xác suất vượt qua 50%. Đây là *kỳ vọng*, dùng lập kế hoạch
  vận hành.
* **P75** — vượt qua 75% số năm. Thận trọng hơn.
* **P90** — vượt qua 90% số năm. Đây là mức **ngân hàng** dùng để tính
  khả năng trả nợ, vì họ cần con số gần như chắc chắn đạt.

Khai một mức rồi gọi nó là "kế hoạch" thì mọi câu hỏi về rủi ro sản
lượng đều mất chỗ trả lời — mà câu hỏi ấy luôn được hỏi, chỉ là hỏi lúc
nào.

Thứ tự là RÀNG BUỘC, không phải quy ước
----------------------------------------
Càng chắc chắn đạt thì con số càng phải **thấp**, nên P50 ≥ P75 ≥ P90.
Người khai hay nhầm chiều — nhầm thì mọi phân tích rủi ro sau đó lộn
ngược mà vẫn chạy trơn tru, không có gì báo. Hệ chặn ngay lúc lưu, kèm
lời giải thích vì sao.

Rải theo ngày là QUY ƯỚC, và hệ nói rõ thế
-------------------------------------------
Mục tiêu khai theo THÁNG. Muốn so luỹ kế giữa tháng thì phải rải ra
từng ngày, mà gió không thổi đều suốt tháng — chia đều chỉ là xấp xỉ.
Hệ vẫn chia đều, nhưng **trả kèm cờ "chia đều"** để nơi in ra nói được
điều đó, chứ không trình bày như mục tiêu riêng của ngày hôm ấy. Ai
không chấp nhận xấp xỉ thì chọn *không rải*, và khi đó giữa tháng hệ
trả lời thẳng là **chưa có gì để so**.

Chưa khai thì nói, không trả 0
-------------------------------
Mục tiêu bằng 0 đọc ra là *"tháng này không cần phát gì"* — ngược hẳn
sự thật là *"chưa ai khai"*. Nên chưa khai thì trả về *không đo được*
kèm lý do, và nơi in ra để trống thay vì in số không.

Một bảng, hai nơi dùng
-----------------------
Tờ báo cáo ngày in luỹ kế tháng cạnh cả ba đường mục tiêu; phần phân
tích sản lượng đa kỳ cũng cần đúng bảng này. **Hai bảng là hai con số
cho cùng một tháng**, và tới lúc lệch thì không ai biết bên nào mới.
""",
    'author': 'BSD Insight',
    'website': 'https://bsdinsight.com',
    'license': 'LGPL-3',
    'depends': ['eam_core'],
    'data': [
        'security/ir.model.access.csv',
        'views/eam_energy_target_views.xml',
    ],
    'installable': True,
}
