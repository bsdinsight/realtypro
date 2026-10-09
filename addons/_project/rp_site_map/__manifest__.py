# -*- coding: utf-8 -*-
{
    'name': 'EPCOne — Bản đồ hiện trường',
    'version': '19.0.1.0.0',
    'category': 'EPCOne',
    'summary': 'Đưa bản đồ hiện trường của EAMOne vào EPCOne và nối nó '
               'với dự án.',
    'description': """
Cầu nối bản đồ hiện trường sang EPCOne
======================================

Bản đồ vốn dựng cho EAMOne (vận hành), nhưng nó trả lời đúng câu của
giai đoạn XÂY DỰNG: *vị trí nào đã dựng máy, vị trí nào chưa, vị trí nào
đã dựng mà chưa chạy được*. Module này đưa nó vào EPCOne ở
**Xây dựng → Hiện trường → Bản đồ hiện trường**, và nối với dự án.

Vì sao nối từ DỰ ÁN sang VỊ TRÍ, không phải chiều ngược lại
------------------------------------------------------------
Một vị trí chức năng sống **lâu hơn** dự án tạo ra nó. Trụ tua-bin số 7
được dựng bởi dự án xây lắp, rồi vận hành 25 năm, rồi có thể được một dự
án nâng cấp khác động tới. Gắn ``project_id`` lên vị trí là ngầm bảo
"chỗ này thuộc về dự án đó" — đúng trong năm đầu, sai suốt phần đời còn
lại, và sai lặng lẽ.

Nối theo chiều này thì dự án chỉ ra nhà máy nó đang làm, còn vị trí vẫn
trung lập. Muốn biết vị trí nào do dự án nào dựng thì đó là câu hỏi của
cầu bàn giao, trả lời bằng chứng từ bàn giao chứ không bằng một ô khai
tay.

Một con số đáng nhìn trước khi đem bản đồ đi họp
------------------------------------------------
``site_no_coords`` — số vị trí thiết bị **chưa có toạ độ**. Chúng không
cắm lên bản đồ được, nên bản đồ trông đầy đủ trong khi thực tế đang
thiếu. Đưa thẳng con số đó lên form dự án.
""",
    'author': 'BSD Insight',
    'website': 'https://bsdinsight.com',
    'license': 'AGPL-3',
    'depends': ['eam_map', 'rp_site', 'rp_estimate'],
    'data': ['views/rp_site_map_views.xml'],
    'installable': True,
}
