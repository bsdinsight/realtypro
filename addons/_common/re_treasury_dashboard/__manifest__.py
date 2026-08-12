# -*- coding: utf-8 -*-
{
    'name': 'Realty Treasury — Dashboard Vốn & Ngân quỹ',
    'version': '19.0.2.0.4',
    'category': 'Realty/Loan',
    'summary': 'Ba dashboard theo ba vai: bức tranh vốn (GĐ tài chính) · '
               'việc hôm nay (cán bộ vay) · vốn theo dự án (chỉ huy '
               'trưởng).',
    'description': """
Hiện thực bản thiết kế "RealtyPro Dashboard Vốn & Ngân quỹ".

Chia màn theo AI MỞ NÓ MỖI SÁNG và ĐỂ QUYẾT CÁI GÌ, không chia theo
module — vì trước đó một dashboard 30 thẻ số dùng chung cho ba vai rất
khác nhau, ai cũng phải lọc bằng mắt phần không liên quan tới mình.

  ① Bức tranh vốn   — đang nợ bao nhiêu, còn rút được bao nhiêu, tháng
                      tới có kẹt tiền không, chỗ nào đỏ. Trần cứng 12 thẻ.
  ② Việc hôm nay    — danh sách việc, mỗi ô bấm ra đúng bản ghi cần xử.
                      Ô bằng 0 làm mờ chứ không ẩn, để thấy rõ "đã sạch".
  ③ Vốn theo dự án  — gộp 4 màn vốn dĩ rời nhau (Nhu cầu vốn · Bảng chỉ
                      tiêu · Năng lực trả nợ §8 · Dòng tiền & DSCR) thành
                      một dòng cho mỗi dự án, mở rộng ra xem chi tiết.

Kỹ thuật: HTML + SVG sinh từ máy chủ rồi nhúng vào form, đúng lối đã có
của re_loan_dashboard và re_cashflow — không thêm asset bundle, không
phụ thuộc thư viện biểu đồ, không gọi CDN. Đổi tab bằng nút thật trên
header; mở rộng thẻ dự án bằng <details> của HTML thuần, không cần
JavaScript.
""",
    'author': 'BSD Insight',
    'website': 'https://bsdinsight.com',
    'license': 'LGPL-3',
    'depends': [
        're_loan_borrowing_base',
        # Hai phụ thuộc dưới đây KHÔNG phải vì cần code, mà để module
        # này luôn nạp SAU CÙNG và là nơi duy nhất chốt menu gốc —
        # trước đó ba module cùng sửa menu gốc, ghi đè lẫn nhau.
        're_loan_dashboard',
        're_treasury_menu',
        're_cashflow',
        're_guarantee',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/re_treasury_dashboard_views.xml',
    ],
    'installable': True,
    'application': False,
}
