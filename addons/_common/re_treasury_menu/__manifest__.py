# -*- coding: utf-8 -*-
{
    'name': 'Realty Treasury — Gom menu Vốn & Ngân quỹ',
    'version': '19.0.2.0.0',
    'category': 'Realty/Loan',
    'summary': 'Gom Vay · Bảo lãnh · Dòng tiền · Đối soát ngân hàng về MỘT '
               'menu gốc "Vốn & Ngân quỹ (Treasury)".',
    'description': """
Vì sao cần module này
=====================

Tài liệu bán hàng mô tả một BỘ duy nhất — "Quản lý Vốn & Ngân quỹ
(Treasury)" — nhưng trên màn hình khách thấy **bốn menu gốc rời nhau**:

  Quản lý Vay · Thuê tài sản · Ngân quỹ (đúng 1 mục con) ·
  Đối soát ngân hàng (2 mục con)

Mở hệ thống lên không thấy cái "bộ" mà tài liệu nói, còn thanh menu thì
bị chiếm 4 chỗ cho những nhánh 1-2 mục.

KHÔNG gom "Thuê tài sản" (anh Đại chốt 2026-08-11): "bộ" trong tài liệu
là bộ BÁN, không phải cây menu. Quá nửa nhánh đó — tài sản thuê, nhật ký
bảo trì, luân chuyển dự án, đổi/trả tài sản — là vận hành CÔNG TRƯỜNG,
người dùng khác hẳn với người dùng tín dụng. Phần thuộc Treasury thật sự
là nghĩa vụ tài chính của thuê tài chính, đã lên dashboard Vay qua
re_lease_loan_bridge.

Cách làm: đổi `parent_id` của các menu gốc kia bằng `<record>` trong XML
— KHÔNG dùng SQL hay post_init_hook, vì cả hai đều bị revert mỗi lần
nâng cấp module nguồn (menu không phải noupdate). Module này phụ thuộc
đúng các module bị gom nên luôn nạp SAU chúng.

Gỡ module ⇒ menu trả về vị trí gốc (khai lại khi nâng cấp module nguồn).

CHƯA gom: "Thư viện đơn giá" (module `rp_cost_library` nằm ở repo
Enterprise) — gom sẽ tạo phụ thuộc Community → Enterprise. Xử riêng ở
phía Enterprise.
""",
    'author': 'BSD Insight',
    'website': 'https://bsdinsight.com',
    'license': 'LGPL-3',
    'depends': [
        're_loan',
        're_lease',
        're_cashflow',
        're_bank_sync',
        # phụ thuộc thêm để gom được menu của chúng vào nhóm nghiệp vụ
        're_guarantee',
        're_loan_borrowing_base',
        're_loan_account',
    ],
    'data': [
        'views/menu_treasury.xml',
    ],
    'installable': True,
    'application': False,
}
