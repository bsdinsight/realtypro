# -*- coding: utf-8 -*-
{
    'name': 'EAMOne — Khuôn bảng điều khiển',
    'version': '19.0.1.0.0',
    'category': 'EAMOne',
    'summary': 'Bảng màu, nhịp chữ và các khối dựng sẵn dùng chung cho mọi '
               'bảng điều khiển EAMOne.',
    'description': """
Khuôn bảng điều khiển EAMOne
============================

Module này KHÔNG có màn hình nào. Nó chỉ giữ một tệp SCSS dùng chung,
để nhiều bảng điều khiển do nhiều người làm vẫn ra một phong cách.

Lấy nguyên cấu trúc và nhịp của bảng EVM (``rp_evm``) — thứ đã chạy
thật và đã trả giá cho mấy cái bẫy bố cục — rồi đổi dải màu sang
NAVY–TEAL của bộ nhận diện.

**Luật dùng:** màn nào cần nét riêng thì thêm lớp con dưới ``.eam-dash``.
KHÔNG sửa biến gốc trong tệp chung — sửa ở đó là đổi luôn màn của người
khác, và người ta chỉ phát hiện khi mở ra thấy màu lạ.

Xem ``KHUON.md`` để biết danh sách lớp và hợp đồng giữa các màn.
""",
    'author': 'BSD Insight',
    'website': 'https://realtypro.vn',
    'license': 'LGPL-3',
    'depends': ['eam_core'],
    'assets': {
        'web.assets_backend': [
            'eam_dashboard/static/src/scss/eam_dash.scss',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
