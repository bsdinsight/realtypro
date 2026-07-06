# -*- coding: utf-8 -*-
{
    'name': 'Realty — Thuê tài sản (Lease)',
    'version': '19.0.1.0.0',
    'category': 'Realty/Lease',
    'summary': 'Quản lý thuê tài sản 2 chiều × 2 loại: Đi thuê / Cho thuê '
               'lại × Hoạt động / Tài chính. Lịch gốc+lãi, kế toán tích '
               'hợp, back-to-back cho thuê lại.',
    'description': """
Realty — Thuê tài sản (re_lease)
================================

App ĐỘC LẬP với Quản lý Vay (quyết định kiến trúc: nghiệp vụ khác —
đối tác leasing/nhà thầu phụ, tài sản vật lý, 2 chiều), nhưng lịch
thanh toán thuê TÀI CHÍNH viết theo pattern gốc+lãi dư nợ giảm dần đã
kiểm chứng ở KW.

Ma trận 2×2 trên ``re.lease.contract``:

- **direction**: Đi thuê (in) / Cho thuê lại (out)
- **lease_type**: Hoạt động (operating) / Tài chính (finance)

Tính năng Phase 1:

- Tài sản thuê (mô tả, serial, giá trị) per HĐ.
- Lịch thanh toán: TÀI CHÍNH = tách GỐC + LÃI (gốc đều hoặc niên kim),
  HOẠT ĐỘNG = tiền thuê đều theo kỳ (tháng/quý/6T/năm).
- **Kế toán tích hợp** (quyết định CC1 — ngay từ đầu):
  - Đi thuê TC: bút toán ghi nhận tài sản thuê TC (Nợ TS thuê TC / Có
    Nợ gốc thuê TC) + mỗi kỳ 1 HÓA ĐƠN NCC 2 dòng (lãi → CP lãi thuê,
    gốc → giảm Nợ gốc thuê TC) — thanh toán hóa đơn là xong kỳ.
  - Đi thuê HĐ: mỗi kỳ 1 hóa đơn NCC (tiền thuê → TK chi phí).
  - Cho thuê lại HĐ: mỗi kỳ 1 hóa đơn BÁN (doanh thu cho thuê).
  - Cho thuê lại TC: mỗi kỳ 1 hóa đơn BÁN 2 dòng (lãi → doanh thu tài
    chính, gốc → giảm Phải thu thuê TC). Bút toán chuyển tài sản sang
    phải thu (derecognition) Phase 1 làm tay — ghi chú trên form.
- **Back-to-back**: HĐ cho thuê lại link HĐ đi thuê gốc → HĐ gốc hiện
  doanh thu cho thuê lại vs chi phí đi thuê + chênh lệch.
- Hóa đơn qua chuẩn account.move → dòng chi phí thuê gắn được hạng mục
  (AC của EVM) qua rp_cost_actual nếu cài.

Phase 2 (sau): khấu hao tự động tài sản thuê TC, dashboard SVG, docs.
""",
    'author': 'BSDInsight',
    'website': 'https://bsdinsight.com',
    'license': 'LGPL-3',
    'depends': [
        're_base',
        'account',
        'mail',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/re_lease_views.xml',
    ],
    'application': True,
    'installable': True,
}
