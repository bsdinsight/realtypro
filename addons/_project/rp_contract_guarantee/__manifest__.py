# -*- coding: utf-8 -*-
{
    'name': 'Realty Project - Contract Guarantees',
    'version': '19.0.1.5.0',
    'category': 'Realty/Project',
    'summary': 'Sổ bảo lãnh hợp đồng nhà thầu — BL nhận từ nhà thầu phụ '
               '(thực hiện HĐ / tạm ứng / bảo hành), upload tài liệu, '
               'cảnh báo hết hạn. Tách khỏi Quản lý Vay.',
    'description': """
Realty Project - Bảo lãnh hợp đồng nhà thầu (rp_contract_guarantee)
==================================================================

Sổ đăng ký tập trung các **bảo lãnh nhà thầu phụ nộp về** cho tổng thầu
(mình là bên thụ hưởng) — hoàn thiện phần bảo lãnh vốn đang là field
phẳng trên rp.contract.

Chiều nghiệp vụ: nhà thầu phụ → NH/bảo hiểm của họ phát hành → bảo lãnh
cho mình. KHÔNG ăn hạn mức tín dụng của mình, KHÔNG phát sinh phí cho
mình → độc lập hoàn toàn với Quản lý Vay.

Phạm vi:
  - rp.contract.guarantee: 3 loại (thực hiện HĐ / tạm ứng / bảo hành),
    4 hình thức bảo đảm (thư BL NH / bảo hiểm bảo lãnh / đặt cọc / ký quỹ)
  - Vòng đời: nháp → hiệu lực → hoàn trả / yêu cầu thanh toán (claim) / hủy
  - % giá trị HĐ + cảnh báo ngoài 2–10% (Luật Đấu thầu 2023)
  - Trục ngày hết hạn + tình trạng hạn + cron cảnh báo sắp hết hạn
  - Phụ lục gia hạn / điều chỉnh (tự áp vào chứng thư)
  - Upload thư bảo lãnh (PDF/scan)
  - Smart button + O2M trên form HĐ nhà thầu (thay 12 field phẳng)
  - Sổ tập trung + báo cáo BL sắp/đã hết hạn
  - post_init: migrate field bảo lãnh phẳng cũ → bản ghi

Căn cứ: Luật Đấu thầu 2023 (bảo đảm thực hiện HĐ 2–10%, hiệu lực đến
hoàn thành nghĩa vụ/chuyển bảo hành, hình thức gồm bảo hiểm bảo lãnh),
Thông tư 11/2022/TT-NHNN.
    """,
    'author': 'BSDInsight',
    'website': 'https://bsdinsight.com',
    'license': 'AGPL-3',
    'depends': [
        'rp_contract',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_cron_data.xml',
        'views/rp_contract_guarantee_views.xml',
        'views/rp_contract_views.xml',
        'views/menu.xml',
    ],
    'post_init_hook': 'post_init_migrate_flat_guarantees',
    'installable': True,
    'application': False,
    'auto_install': False,
}
