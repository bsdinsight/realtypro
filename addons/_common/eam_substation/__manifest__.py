# -*- coding: utf-8 -*-
{
    'name': 'EAMOne — Trạm biến áp',
    'version': '19.0.1.0.0',
    'category': 'EAMOne',
    'summary': 'Cây cấu phần trạm biến áp nâng áp và mẫu cấu trúc TBA-STD '
               '— dùng chung cho nhà máy điện gió, điện mặt trời và mọi '
               'nguồn phát khác.',
    'description': """
EAMOne — Trạm biến áp
======================

Vì sao đứng riêng một module
-----------------------------
Trạm nâng áp có ở **mọi** nhà máy điện, không riêng gió hay mặt trời.
Đặt nó trong ``eam_wind`` thì nhà máy quang điện không có trạm; đặt
trong ``eam_core`` thì lõi hoá ra chứa nội dung của một ngành. Nên nó
là mảnh đầu tiên của **nhánh BOP dùng chung** mà cây cấu phần điện mặt
trời đã nói trước tới: *"Trạm nâng áp, cáp ngầm, SCADA không nằm ở đây
— chúng thuộc nhánh BOP dùng chung cho mọi loại nhà máy."* Cáp ngầm và
SCADA sẽ vào cùng module này khi tới lượt.

Chọn gì làm một vị trí
-----------------------
Cùng tiêu chí đã dùng cho tua-bin: chỉ lập vị trí chức năng cho thứ
**thay được tại chỗ và đáng theo dõi lịch sử theo sê-ri**. Máy cắt,
rơ-le, bộ điều áp dưới tải, ắc-quy, công tơ giao nhận đều đạt cả hai.
Thanh cái, sứ xuyên thì lập ở mức cụm chứ không tách từng cái.

Công tơ giao nhận (``MET``) để ở **cấp một** chứ không nhét vào ngăn lộ:
nó là chỗ tiền đi qua, và khi tranh chấp sản lượng thì người ta hỏi
đúng con công tơ ấy — số chế tạo, ngày kiểm định, lần thay gần nhất.
""",
    'author': 'BSD Insight',
    'license': 'LGPL-3',
    'depends': ['eam_core'],
    'data': [
        'data/eam_substation_category_data.xml',
        'data/eam_substation_structure_data.xml',
    ],
    'installable': True,
    'application': False,
}
