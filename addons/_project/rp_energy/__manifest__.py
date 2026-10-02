# -*- coding: utf-8 -*-
{
    'name': 'Realty — Dự án năng lượng tái tạo',
    'version': '19.0.1.2.0',
    'category': 'Realty/Project',
    'summary': 'Điện gió / điện mặt trời: loại dự án, công suất, ngày COD, '
               'gói thầu HV / TSA / BOP — giấu phần bán hàng bất động sản.',
    'description': """
Realty — Dự án năng lượng tái tạo (rp_energy)
=============================================

Bộ `rp_*` dựng cho dự án bất động sản: dự án có phân khu, toà nhà, căn
hộ, có đợt mở bán và có khách mua. Chủ đầu tư nhà máy điện dùng CÙNG bộ
nghiệp vụ đó — hợp đồng, gói thầu, tiến độ, nghiệm thu, thanh toán,
dòng tiền — nhưng KHÔNG có căn hộ để bán, và từ vựng thì lệch hẳn:
"Chung cư", "Phân khúc thị trường", "Mở bán" không có nghĩa gì với một
cánh đồng gió.

Module này KHÔNG thêm nghiệp vụ mới. Nó chỉ:

* thêm loại dự án **Điện gió / Điện mặt trời / Thuỷ điện / Lưu trữ pin**;
* thêm vài ô riêng của ngành: công suất (MW), số tua-bin, ngày vận hành
  thương mại (COD), ngày đóng điện, bên mua điện (PPA);
* **giấu** những ô và tab chỉ dành cho bán bất động sản khi dự án là
  dự án năng lượng (phân khúc, mở bán, marketing, liên hệ bán hàng,
  kiểu phát triển cao tầng/thấp tầng);
* phân loại gói thầu theo cách ngành điện chia việc: **HV** (trạm nâng
  áp và đấu nối), **TSA** (cung cấp tua-bin), **BOP** (hạ tầng và xây
  lắp phần còn lại), **O&M**.

Giấu chứ không xoá: dữ liệu cũ và các dự án bất động sản không đổi gì.
    """,
    'author': 'BSDInsight',
    'website': 'https://bsdinsight.com',
    'license': 'AGPL-3',
    'depends': [
        're_base',
        'rp_estimate',
        'rp_cost_base',
        # Mốc COD là đích của đường găng toàn dự án (_rp_schedule_deadline).
        'rp_schedule',
    ],
    'data': [
        'views/re_project_views.xml',
        'views/rp_tender_package_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
