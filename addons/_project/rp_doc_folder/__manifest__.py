# -*- coding: utf-8 -*-
{
    'name': 'Realty Project — Bộ thư mục hồ sơ dự án (EPC)',
    'version': '19.0.1.0.0',
    'category': 'Realty/Project',
    'summary': 'Cây thư mục chuẩn theo vòng đời EPC, dựng sẵn cho mỗi '
               'dự án; chỗ neo để đẩy file sang SharePoint về sau.',
    'description': """
Realty Project — Bộ thư mục hồ sơ dự án (rp_doc_folder)
=======================================================

Vì sao dựng sẵn chứ không để trống
----------------------------------
Thư mục để trống thì mỗi dự án tự mọc một cây khác nhau, và sau hai năm
không ai tìm được hồ sơ của dự án mình không làm. Quan trọng hơn: cây
thư mục chuẩn là một **danh mục những thứ phải có**. Mở ra thấy ô
"12.2 Tài liệu vận hành & bảo trì" còn rỗng ba tháng trước ngày bàn
giao thì biết ngay là sắp có chuyện — mà điều 5.7 của hợp đồng nói rõ
thiếu nó thì ngày bàn giao chưa chạy và phạt chậm vẫn đếm.

Bài học lấy từ Procore
----------------------
Procore KHÔNG công bố một bộ thư mục chuẩn nào. Hướng dẫn của họ là tự
dựng cây trong project template rồi nhân sang dự án sau. Nhưng họ nói
rõ một điều ngược với trực giác, và đó mới là thứ đáng học:

    *"Procore does not recommend that you create folders for files that
    would otherwise live in a Procore tool."*

Tức là đừng tạo thư mục cho thứ đã có sổ riêng. Hệ thống này đã có sổ
hồ sơ trình (rp.document, đồng hồ 21 ngày), sổ phát sinh, sổ khiếu nại,
nhật ký công trường, biên bản nghiệm thu, sổ bảo lãnh. Tạo thêm thư mục
"Phát sinh" rời là lập tức có hai nguồn sự thật.

Nên ở đây mỗi thư mục khai được **nó là bãi đáp file của sổ nào**
(``tool_model_id``). Phân vai rõ: **thư mục giữ file, sổ giữ ý nghĩa.**
Thư mục có sổ thì mở ra là nút nhảy thẳng sang sổ, không phải chỗ thả
file rời.

Cây mặc định là vòng đời EPC phía CHỦ ĐẦU TƯ: 00 quản lý → 01 pháp lý →
02 tài chính → 03 đấu thầu & hợp đồng → 04 thiết kế → 05 mua sắm → 06
thi công → 07 chất lượng → 08 HSE → 09 tiến độ → 10 chạy thử → 11 thanh
toán → 12 bàn giao.
""",
    'author': 'BSD Insight',
    'website': 'https://bsdinsight.com',
    'license': 'AGPL-3',
    'depends': ['re_base', 'rp_estimate'],
    'data': [
        'security/ir.model.access.csv',
        'data/rp_doc_folder_template_data.xml',
        'views/rp_doc_folder_views.xml',
        'views/re_project_views.xml',
    ],
    'installable': True,
}
