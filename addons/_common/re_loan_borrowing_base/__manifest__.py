# -*- coding: utf-8 -*-
{
    'name': 'Realty Loan — Borrowing Base (Hạn mức khả dụng)',
    'version': '19.0.2.3.0',
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
- **KW**: cảnh báo (không chặn — theo quyết định của khách hàng) khi số tiền KW
  vượt khả dụng thực tế của facility.

HĐTD/facility KHÔNG có pledge nào → bỏ ràng buộc base tương ứng
(coi như không quản TSBĐ trên hệ thống) — không phá dữ liệu hiện có.

Phạm vi (từ 19.0.2.0.0)
-----------------------
Module này KHÔNG phụ thuộc module thi công. Phần cần dữ liệu hợp đồng
với CĐT / IPC / dự toán / tiến độ — nhu cầu vốn dự án, dòng tiền dự án
& DSCR, năng lực trả nợ, rà soát tuần, bảng chỉ tiêu, checklist giải
ngân, quyền đòi nợ làm TSBĐ — nằm ở ``re_loan_bb_project``, tự cài khi
có đủ các module đó.
""",
    'author': 'BSDInsight',
    'website': 'https://bsdinsight.com',
    'license': 'AGPL-3',
    # KHÔNG phụ thuộc module thi công (rp_*). Phần cần dữ liệu hợp
    # đồng CĐT / dự toán / tiến độ nằm ở re_loan_bb_project — tách ra
    # để bộ vay chạy được độc lập ở khách chỉ mua phân hệ vay.
    'depends': [
        're_loan',
        're_loan_dashboard',
        # TK kiểm soát dòng tiền trỏ tới account.account (backlog 754).
        'account',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/re_loan_borrowing_base_rules.xml',
        # re_loan_project_axis_views.xml nạp TRƯỚC: cả nó và
        # re_loan_borrowing_views.xml cùng kế thừa form HĐTD, mà Odoo
        # xác thực view trên trạng thái DB HIỆN TẠI. Khi nâng cấp bản
        # đã tách module, arch CŨ của tab "Hạn mức theo dự án" còn cột
        # contract_id (trường của bộ thi công, nay nạp sau) — file kia
        # parse trước là đổ nguyên lượt nâng cấp.
        'views/re_loan_project_axis_views.xml',
        'views/re_loan_borrowing_views.xml',
        'views/re_loan_credit_contract_views.xml',
        'views/re_loan_pledge_allocation_views.xml',
        'views/re_loan_facility_reallocate_views.xml',
        'views/re_loan_dashboard_views.xml',
    ],
    'installable': True,
    'application': False,
}
