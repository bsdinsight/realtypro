# -*- coding: utf-8 -*-
{
    'name': 'EPCOne — Sổ phát sinh (Variation)',
    'version': '19.0.1.0.0',
    'category': 'Realty/Project',
    'summary': 'Thay đổi phạm vi theo điều 13: đồng hồ báo giá 14 ngày, '
               'giá theo đơn giá hợp đồng, ra phụ lục và vào dự báo chi phí.',
    'description': """
EPCOne — Sổ phát sinh (rp_variation)
============================================

Câu hỏi của chủ đầu tư luôn là "nhà thầu phát sinh khối lượng so với hợp
đồng thì ngân sách dự án ra sao". Trả lời được cần bốn thứ đi cùng nhau:

* **Nguồn gốc**: chủ đầu tư chỉ thị · yêu cầu nhà thầu báo giá · nhà thầu
  tự đề xuất (value engineering) · thay đổi pháp luật · làm theo ngày
  công. Mỗi nguồn gốc kéo theo quyền và nghĩa vụ khác nhau.
* **Đồng hồ 14 ngày của điều 13**: nhà thầu phải báo giá trong 14 ngày kể
  từ khi được yêu cầu, và chỉ có 14 ngày để phản đối một chỉ thị, với
  đúng bốn lý do hợp đồng cho phép (không mua được vật tư, giảm an toàn,
  ảnh hưởng cam kết hiệu suất, không khả thi kỹ thuật).
* **Căn cứ giá**: điều 13.3 buộc dùng ĐƠN GIÁ TRONG HỢP ĐỒNG khi có; không
  có mới tính chi phí + lợi nhuận hợp lý. Từng dòng khối lượng ghi rõ đơn
  giá lấy từ hợp đồng hay không — lúc đàm phán mới cãi được.
* **Đi tới đâu**: phát sinh duyệt xong phải ra **phụ lục điều chỉnh giá**
  (một nút), và phải cộng vào **dự báo chi phí cuối kỳ** của dự án.

Màn hình dự án đặt bốn con số cạnh nhau: ngân sách duyệt (BAC) · đã cam
kết theo hợp đồng · phát sinh đã duyệt và đang chờ · dự báo chi phí cuối
kỳ — kèm cảnh báo khi dự báo vượt ngân sách. Cột "đang chờ" là bắt buộc:
phát sinh chưa duyệt vẫn phải trả nếu việc đã làm ngoài hiện trường.

Phát sinh có kéo dài thời gian thì mở thẳng hồ sơ khiếu nại gia hạn
(rp_claim) từ chính phát sinh đó.
""",
    'author': 'BSDInsight',
    'website': 'https://bsdinsight.com',
    'license': 'LGPL-3',
    'depends': [
        'rp_contract',
        'rp_cost_base',
        'rp_evm',
        'rp_claim',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_sequence.xml',
        'views/rp_variation_views.xml',
        'views/re_project_views.xml',
        'views/rp_contract_views.xml',
        'views/rp_variation_menus.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
