# -*- coding: utf-8 -*-
{
    'name': 'EAMOne — Kho phụ tùng',
    'version': '19.0.1.0.0',
    'category': 'EAMOne',
    'summary': 'Kho phụ tùng cho bảo trì: hồ sơ phụ tùng, giữ chỗ, cấp '
               'phát theo lệnh công việc, hoàn trả và trạng thái hàng.',
    'description': """
Vì sao phải có module này
=========================

``eam.work.order.part`` ghi **chi phí** vật tư đã dùng. Nó không trừ kho,
và cố ý như vậy: ``eam_work_order`` không phụ thuộc ``stock``, nên khách
chạy EAMOne mà không dùng kho Odoo vẫn ghi được chi phí.

Hậu quả nếu dừng ở đó thì nặng và **im lặng**: tồn kho không bao giờ giảm
vì bảo trì. Tháng này thay 12 bộ lọc, sổ kho vẫn báo đủ 24 cái. Cảnh báo
"dưới định mức" không bao giờ kêu, cho tới hôm cần vật tư mới phát hiện
kho rỗng — mà sổ vẫn nói là còn.

Module này là **cây cầu**: ai cài cả ``eam_work_order`` lẫn ``stock`` thì
cài thêm nó, và từ đó mỗi dòng vật tư trên lệnh công việc sinh ra một
phiếu xuất kho thật.

Ba luật
-------

**① Xuất rồi thì không xuất lại.** Mỗi dòng vật tư giữ con trỏ tới phiếu
xuất của chính nó. Bấm nút lần hai chỉ xuất những dòng chưa xuất.

**② Vật tư quay vòng phải chỉ đích danh sê-ri.** Hộp số, máy phát, cánh,
bộ biến đổi — hãng chỉ bảo hành con mang đúng số sê-ri đó. Để hệ thống tự
chọn một con bất kỳ trong kho là vứt đi quyền đòi bảo hành. Nên thiếu
sê-ri thì chặn, không đoán.

**③ Đóng lệnh mà còn vật tư chưa xuất thì chặn.** Đây là chốt giữ cho hai
sổ không trôi khỏi nhau. Vật tư mua thẳng cho việc này, hoặc hãng cấp
theo bảo hành, thì không đi qua kho — đánh dấu **Không qua kho** là xong.
Chặn ở đây phiền một lần, còn để hai sổ lệch thì không ai phát hiện ra.

Vật tư đi đâu sau khi xuất
---------------------------
Hai đích khác nhau, vì hai thứ khác nhau:

* **Tiêu dùng bảo trì** — dầu, lọc, mỡ, má phanh. Dùng là hết.
* **Đã lắp lên thiết bị** — vật tư quay vòng. Nó chưa mất đi, nó đang nằm
  trong máy. Nơi ghi nhận "đang nằm ở trụ nào" là sổ lắp đặt
  (``eam.installation``), không phải sổ kho — **một việc một sổ**, không
  ghi hai nơi rồi lệch.

Con đã tháo ra, nếu còn sửa được, nằm ở vị trí *Chờ đại tu* và chỉ quay
lại kho khi đã sửa xong và nghiệm thu.
""",
    'author': 'BSD Insight',
    'website': 'https://bsdinsight.com',
    'license': 'AGPL-3',
    'depends': ['eam_work_order', 'eam_pm', 'eam_qr', 'stock', 'purchase'],
    'data': [
        'security/eam_stock_security.xml',
        'security/ir.model.access.csv',
        'data/eam_stock_data.xml',
        'data/eam_inbound_data.xml',
        'data/eam_material_data.xml',
        'data/eam_rotable_data.xml',
        'data/eam_tool_data.xml',
        'data/eam_adjustment_data.xml',
        # Nhóm menu phải nạp TRƯỚC mọi file view khác —
        # 17 mục menu của kho nằm rải ở bảy file.
        'views/eam_stock_menus.xml',
        'views/eam_stock_views.xml',
        'views/eam_part_views.xml',
        'views/eam_user_views.xml',
        'views/eam_inbound_views.xml',
        'views/eam_material_views.xml',
        'views/eam_rotable_views.xml',
        'views/eam_tool_views.xml',
        'views/eam_adjustment_views.xml',
        'views/eam_demand_views.xml',
        'views/eam_final_views.xml',
    ],
    'installable': True,
}
