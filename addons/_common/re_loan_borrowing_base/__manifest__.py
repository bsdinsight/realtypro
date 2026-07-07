# -*- coding: utf-8 -*-
{
    'name': 'Realty Loan — Borrowing Base (Hạn mức khả dụng)',
    'version': '19.0.1.4.0',
    'category': 'Realty/Loan',
    'summary': 'Cơ sở bảo đảm 2 tầng cho tổng thầu: quyền đòi nợ tự định '
               'giá theo sản lượng + tỷ lệ cho vay + khả dụng thực tế + '
               'cảnh báo margin call.',
    'description': """
Realty Loan — Borrowing Base (re_loan_borrowing_base)
=====================================================

Mô hình NH cho tổng thầu vay theo cơ sở bảo đảm động (borrowing base):

**Khả dụng(facility) = min(**
  ① HM facility − dư nợ facility            *(cam kết riêng)*
  ② base riêng facility − dư nợ facility    *(ring-fence, khi có TSBĐ riêng)*
  ③ base toàn HĐTD − dư nợ toàn HĐTD        *(umbrella)*
**)**

Thành phần:

- **TSBĐ Quyền đòi nợ**: collateral gắn HĐ với CĐT
  (``rp.owner.contract``) → giá trị TỰ ĐỘNG = khoản phải thu (floor 0).
  Mỗi lần BBNT được CĐT duyệt / CĐT thanh toán → tự sinh bản ghi định
  giá (audit trail như NH đánh giá lại theo kỳ).
- **Tỷ lệ cho vay (advance rate %)**: khai trên loại TSBĐ (mặc định),
  override từng pledge. Đóng góp base = giá trị × tỷ lệ. Tỷ lệ = 0
  (chưa khai) → KHÔNG tính vào base (thận trọng kiểu NH).
- **Facility**: base riêng (pledge cấp facility) + khả dụng thực tế +
  cảnh báo margin call khi dư nợ vượt base riêng.
- **HĐTD**: base tổng (mọi pledge) + khả dụng + cảnh báo umbrella.
- **KW**: cảnh báo (không chặn — theo quyết định CC1) khi số tiền KW
  vượt khả dụng thực tế của facility.

HĐTD/facility KHÔNG có pledge nào → bỏ ràng buộc base tương ứng
(coi như không quản TSBĐ trên hệ thống) — không phá dữ liệu hiện có.
""",
    'author': 'BSDInsight',
    'website': 'https://bsdinsight.com',
    'license': 'LGPL-3',
    'depends': [
        're_loan',
        're_loan_dashboard',
        'rp_owner_contract',
    ],
    'data': [
        'views/re_loan_borrowing_views.xml',
        'views/re_loan_dashboard_views.xml',
    ],
    'installable': True,
    'application': False,
}
