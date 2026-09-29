# -*- coding: utf-8 -*-
{
    'name': 'Realty Loan — Borrowing Base × Dự án thi công',
    'version': '19.0.1.0.0',
    'category': 'Realty/Loan',
    'summary': 'Nối borrowing base với hợp đồng CĐT, IPC, dự toán và '
               'tiến độ: quyền đòi nợ, nhu cầu vốn, dòng tiền dự án & '
               'DSCR, năng lực trả nợ, rà soát tuần, checklist giải ngân.',
    'description': """
Realty Loan — Borrowing Base × Dự án thi công (re_loan_bb_project)
==================================================================

Tách ra từ ``re_loan_borrowing_base`` ở bản 19.0.2.0.0.

Vì sao tách
-----------
Lõi borrowing base — phân bổ tài sản bảo đảm, bảo đảm khai ban đầu,
khả dụng thực tế, hạn mức theo dự án — chỉ cần phân hệ vay. Còn các
tính năng dưới đây cần dữ liệu thi công (hợp đồng với CĐT, IPC, dự
toán, tiến độ), kéo theo cả bộ ``rp_*``:

- quyền đòi nợ (IPC) làm tài sản bảo đảm và định giá lại tự động;
- nhu cầu vốn dự án, bảng chỉ tiêu xanh/vàng/đỏ;
- dòng tiền dự án & DSCR, năng lực trả nợ;
- rà soát tuần và danh sách ngoại lệ;
- checklist 8 điều kiện giải ngân.

Khách mua trọn bộ thì Odoo tự cài module này (``auto_install``), không
phải chọn tay. Khách chỉ mua phân hệ vay thì lõi vẫn chạy đủ.
""",
    'author': 'BSDInsight',
    'website': 'https://bsdinsight.com',
    'license': 'LGPL-3',
    'depends': [
        're_loan_borrowing_base',
        'rp_owner_contract',
        'rp_evm',
        'rp_loan_bridge',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/re_loan_project_axis_contract_views.xml',
        'views/re_loan_note_checklist_views.xml',
        'views/rp_owner_ipc_pledge_views.xml',
        'views/re_loan_project_funding_views.xml',
        'views/re_loan_project_cashflow_views.xml',
        'views/re_loan_kpi_views.xml',
        'views/re_loan_repayment_capacity_views.xml',
        'views/re_loan_weekly_review_views.xml',
    ],
    'installable': True,
    'application': False,
    # Đủ borrowing base + bộ thi công thì tự cài lại phần vừa tách ra,
    # để bản đang chạy của khách không mất tính năng sau khi nâng cấp.
    'auto_install': True,
}
