# -*- coding: utf-8 -*-
{
    "name": "EPCOne — Bán điện (PPA)",
    "version": "19.0.1.2.2",
    "category": "Realty/Project",
    "summary": "Hợp đồng mua bán điện, sản lượng theo kỳ và hoá đơn tiền "
               "điện cho chủ đầu tư nhà máy điện.",
    "description": """
Bán điện (rp_ppa)
=================

Doanh thu của chủ đầu tư nhà máy điện KHÔNG phải bán hàng: một bên mua
duy nhất (hoặc vài bên), hợp đồng 20–25 năm, sản phẩm là kWh đo bằng
công-tơ. Không có kho, không có khách tiềm năng, không có chiết khấu.
Port phần bán bất động sản hay phần doanh thu của tổng thầu sang đây là
sai từ gốc.

Bốn bảng:

* **Hợp đồng mua bán điện (PPA)** — bên mua, thời hạn tính từ COD, biểu
  giá có TRƯỢT GIÁ theo năm hợp đồng, tỷ lệ phân bổ sản lượng, điều
  khoản điện chạy thử và sản lượng bị cắt giảm.
* **Điểm giao nhận & công-tơ** — điểm đo, công-tơ chính/đối chứng, hệ số
  tổn thất tới điểm giao.
* **Sản lượng kỳ** — phát gộp − tự dùng − tổn thất = giao nhận ròng, kèm
  sản lượng bị cắt giảm và % khả dụng; phân bổ cho từng PPA.
* **Hoá đơn tiền điện** — sinh `account.move` cho từng PPA của kỳ.

Ba thứ quyết định tiền mà người ngoài ngành hay bỏ sót, và vì vậy được
làm thành trường riêng chứ không gộp:

1. **Sản lượng bị cắt giảm (deemed energy)** — lưới bắt giảm phát thì
   nhà máy VẪN được trả. Với điện gió đấu nối xuyên biên giới đây thường
   là rủi ro doanh thu lớn hơn cả rủi ro gió. Gộp vào sản lượng thật thì
   vĩnh viễn không biết mình mất bao nhiêu vì lưới.
2. **Cam kết khả dụng của hãng tua-bin (FSA)** — thiếu thì HÃNG đền.
   Đó là khoản thu từ NHÀ THẦU, không phải doanh thu bán điện, nên để
   riêng; cộng chung vào doanh thu là che mất việc nhà thầu đang nợ mình.
3. **Trượt giá** — biểu giá theo từng năm hợp đồng, sinh tự động từ giá
   gốc rồi sửa tay được. Một con số giá duy nhất cho 20 năm là sai ngay
   từ năm thứ hai.
    """,
    "author": "BSDInsight",
    "website": "https://bsdinsight.com",
    "license": "AGPL-3",
    "depends": [
        "rp_energy",
        "account",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_sequence.xml",
        "views/menu_root.xml",
        "views/rp_energy_meter_views.xml",
        "views/rp_ppa_views.xml",
        "views/rp_energy_period_views.xml",
        "views/rp_energy_invoice_wizard_views.xml",
        "views/re_project_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
