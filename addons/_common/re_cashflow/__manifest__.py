# -*- coding: utf-8 -*-
{
    'name': 'Realty — Ngân quỹ: Dự báo dòng tiền',
    'version': '19.0.1.0.0',
    'category': 'Realty/Treasury',
    'summary': 'Dự báo dòng tiền 13/26 tuần — tổng hợp mọi nghĩa vụ '
               'thu/chi đã nằm trong hệ thống (vay, thuê, bảo lãnh, hóa '
               'đơn, milestone HĐ nhà thầu).',
    'description': """
Realty — Ngân quỹ: Dự báo dòng tiền (re_cashflow)
=================================================

Lớp tổng hợp treasury: gom mọi dòng tiền TƯƠNG LAI đã có sẵn trong
các module thành 1 lịch dòng tiền theo tuần (13/26 tuần) + số dư dự
kiến + cảnh báo tuần âm.

**Nguồn CHI (out)** — tự phát hiện module nào cài thì lấy nguồn đó
(không hard-depend):
- Kỳ trả nợ KW chưa trả (gốc+lãi+phí còn lại) — re_loan
- Đợt phí bảo lãnh chưa trả — re_guarantee
- Kỳ thuê phải trả CHƯA lên hóa đơn — re_lease (đi thuê)
- Hóa đơn NCC posted chưa trả (mọi nguồn — gồm kỳ thuê/milestone đã
  lên hóa đơn → không đếm trùng)
- Milestone HĐ nhà thầu trạng thái KẾ HOẠCH (chưa hóa đơn) — rp_contract

**Nguồn THU (in):**
- Hóa đơn bán posted chưa thu
- Kỳ cho thuê lại CHƯA lên hóa đơn — re_lease
- Phải thu CĐT (rp_owner_contract) — KPI riêng (chưa có ngày thu dự
  kiến, không đưa vào bucket tuần)

**Đầu ra:** số dư đầu kỳ (Σ TK ngân hàng/tiền mặt), bảng nguồn × tuần
(cột "Quá hạn" riêng), dòng tiền ròng + số dư lũy kế từng tuần, SVG
chart, cảnh báo TUẦN ÂM ĐẦU TIÊN, drill-down từng nguồn.

Nguyên tắc chống đếm trùng: chứng từ đã thành hóa đơn thì tính theo
hóa đơn; lịch/kế hoạch chỉ tính phần CHƯA lên hóa đơn.
""",
    'author': 'BSDInsight',
    'website': 'https://bsdinsight.com',
    'license': 'LGPL-3',
    'depends': ['re_base', 'account'],
    'data': [
        'security/ir.model.access.csv',
        'views/re_cashflow_views.xml',
    ],
    'application': True,
    'installable': True,
}
