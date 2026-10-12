# -*- coding: utf-8 -*-
{
    'name': 'Realty — Ký duyệt điện tử',
    'version': '19.0.1.1.0',
    'category': 'Realty',
    'summary': 'Ký duyệt chứng từ trong hệ thống, kèm mã băm phát hiện '
               'sửa nội dung sau khi ký.',
    'description': """
Ký duyệt điện tử dùng chung
===========================

Một chữ ký chỉ là tấm ảnh thì vô dụng: ký xong sửa số ở dưới, chữ ký
vẫn nằm đó như chưa có gì xảy ra. Nên mỗi lần ký, hệ thống băm phần
NỘI DUNG CHỊU TRÁCH NHIỆM của chứng từ (số ngày gia hạn, số tiền, kỳ
nghiệm thu…) và cất mã băm cùng chữ ký. Mở lại, nó băm lần nữa rồi so:
khác là chữ ký tự báo **không còn hợp lệ**, kèm ngày giờ và người ký.

Mỗi model muốn ký chỉ cần kế thừa ``re.signable`` và viết
``_sign_payload()`` trả về đúng những trường mà chữ ký bảo chứng.

PHẠM VI PHÁP LÝ — nói rõ để không hứa quá:
đây là **chữ ký điện tử** theo Luật Giao dịch điện tử 2023, KHÔNG phải
**chữ ký số** có chứng thư của tổ chức chứng thực (VNPT-CA, Viettel-CA,
FPT-CA). Muốn chữ ký kiểm tra được bằng Adobe Reader thì phải tích hợp
CA — lớp này vẫn dùng lại được khi lên tới đó.
""",
    'author': 'BSD Insight',
    'website': 'https://realtypro.vn',
    'license': 'LGPL-3',
    'depends': ['re_base'],
    'data': [
        'security/ir.model.access.csv',
        'views/re_approval_rule_views.xml',
        'views/re_signature_views.xml',
        'views/re_signable_templates.xml',
        'wizards/re_sign_wizard_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
