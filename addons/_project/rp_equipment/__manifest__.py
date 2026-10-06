# -*- coding: utf-8 -*-
{
    "name": "Realty Project — Sổ lô thiết bị chính",
    "version": "19.0.1.1.0",
    "category": "Realty/Project",
    "summary": "Theo dõi lô thiết bị chính theo chặng vận chuyển: ai chịu "
               "rủi ro ở đoạn nào, bảo hiểm tới đâu, nối mốc thanh toán.",
    "description": """
Sổ lô thiết bị chính (rp_equipment)
===================================

Trong giai đoạn xây dựng, **vật tư là của nhà thầu** — chủ đầu tư không
có kho và không nên có. Dựng phân hệ kho cho chủ đầu tư lúc này là dựng
một cái kho rỗng.

Nhưng với 75,8 triệu USD tua-bin đang đi từ nhà máy ở châu Âu về một
cánh đồng ở Savannakhet, có một câu hỏi phải trả lời được hằng tuần:
**"kiện hàng này đang ở đâu, và nếu nó hỏng thì ai chịu?"**. Phiếu nhập
xuất kho không trả lời được câu đó.

Nên sổ này theo **chặng**, không theo tồn:

    Xuất xưởng → Vận tải biển → Cập cảng → Thông quan
      → Vận chuyển nội địa → Nhập bãi công trường → Lắp dựng

Rủi ro ghi ở **từng chặng** chứ không ở lô: cùng một kiện, đoạn biển là
rủi ro của bên này, đoạn nội địa lại của bên khác. Ghi một "chủ sở hữu"
duy nhất cho cả hành trình là xoá mất chính thông tin cần dùng.

Điều kiện giao hàng cũng ở chặng, vì nó quyết định thời điểm chuyển rủi
ro: **CIF** nghĩa là rủi ro chuyển sang bên mua NGAY KHI hàng lên tàu ở
cảng xuất, dù bảo hiểm vẫn do bên bán mua. Đây là chỗ hay hiểu nhầm
nhất, và hiểu nhầm thì mất tiền.

Lô nối được với **mốc thanh toán** của hợp đồng cung cấp, vì tiền gói
cung cấp trả theo tiến độ giao hàng chứ không theo khối lượng thi công.

Có cảnh báo **bảo hiểm hết hạn trước khi hàng tới nơi** — khoảng trống
đó là lúc không ai chịu nếu có chuyện.
    """,
    "author": "BSDInsight",
    "website": "https://bsdinsight.com",
    "license": "AGPL-3",
    "depends": ["rp_contract", "rp_progress"],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_sequence.xml",
        "views/rp_equipment_lot_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
