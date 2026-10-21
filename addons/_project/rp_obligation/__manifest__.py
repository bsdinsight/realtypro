# -*- coding: utf-8 -*-
{
    'name': 'EPCOne — Sổ nghĩa vụ hợp đồng',
    'version': '19.0.1.1.0',
    'category': 'Realty/Project',
    'summary': 'Điều khoản thành dữ liệu, và MỘT sổ cái trả lời "hợp đồng '
               'này buộc ai làm gì, hạn nào" — chỉ mục sang các sổ đã có, '
               'không chép số liệu.',
    'description': """
EPCOne — Sổ nghĩa vụ hợp đồng (rp_obligation)
==============================================

Hệ thống đã có bốn sổ nghĩa vụ chạy tốt — hồ sơ phải trình (đ. 5.2),
phát sinh (đ. 13), khiếu nại, bảo lãnh — cộng lịch thanh toán trên hợp
đồng. Thứ không có là một chỗ trả lời câu hỏi đơn giản nhất: *hợp đồng
này buộc ai làm gì, hạn nào?*

Module này thêm hai thứ, và cố ý không thêm gì nữa:

**1. Điều khoản thành dữ liệu** (``rp.contract.clause``)

Trước đây "Điều 13.3" nằm trong ``help=`` của trường Python — chữ cho
lập trình viên đọc. Nay là bản ghi có số điều, trang, trích đoạn nguyên
văn, và thuộc bản ký nào. Phụ lục sửa điều khoản thì sinh bản mới trỏ về
bản cũ, không sửa đè: sáu tháng sau vẫn trả lời được *"lúc ký thì hạn là
bao nhiêu ngày"*.

**2. Sổ cái nghĩa vụ** (``rp.obligation``)

Mỗi dòng là **chỉ mục**, không phải bản sao. Hạn và tình trạng là trường
tính, đọc thẳng từ bản ghi gốc — không có đường nào gõ tay đè lên. Sửa
hạn ở sổ gốc là sổ cái đổi theo ngay, nên không bao giờ có chuyện hai sổ
lệch nhau mà cả hai đều trông như đúng.

Một bản ghi có thể sinh **hai** nghĩa vụ của **hai bên**: một hồ sơ phải
trình buộc nhà thầu nộp trước hạn, rồi buộc bên xem xét trả lời trong
hạn. Gộp làm một là giấu mất một bên.

Chưa có trong bản này
---------------------
Bảo hiểm, bảo hành, báo cáo định kỳ, giấy phép (các loại chưa có sổ
chuyên) và lớp đọc hợp đồng bằng máy — thuộc các bản sau. Khung dữ liệu
đã chừa sẵn chỗ.
""",
    'author': 'BSD Insight',
    'website': 'https://bsdinsight.com',
    'license': 'LGPL-3',
    'depends': [
        'rp_contract',
        'rp_document',
        'rp_variation',
        'rp_claim',
        'rp_contract_guarantee',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_sequence.xml',
        'data/ir_cron.xml',
        'views/rp_contract_clause_views.xml',
        'views/rp_obligation_views.xml',
        'views/rp_contract_views.xml',
        'views/clock_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
