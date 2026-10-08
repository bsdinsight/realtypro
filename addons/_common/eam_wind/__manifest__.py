# -*- coding: utf-8 -*-
{
    'name': 'EAMOne — Gói ngành Điện gió',
    'version': '19.0.1.0.0',
    'category': 'EAMOne',
    'summary': 'Cây cấu phần tua-bin gió và hệ thống phụ trợ, theo phân '
               'loại ReliaWind.',
    'description': """
EAMOne Wind Pack
================

Đây là NỘI DUNG, không phải chức năng. Lõi ``eam_core`` dựng cây rỗng;
gói này nạp cây thật của ngành điện gió vào.

Vì sao chọn ReliaWind chứ không phải RDS-PP
-------------------------------------------
RDS-PP (VGB S-823-T32) là bộ đầy đủ nhất — khoảng 2.200 mã, 5 cấp, phủ
cả hạ tầng phụ trợ — và ánh xạ MỘT CHIỀU: ReliaWind và NERC-GADS quy
được về RDS-PP, ngược lại thì không. FGW TG7 D3 bắt buộc dùng nó cho hồ
sơ bảo trì điện gió ở Đức và châu Âu.

Nhưng **RDS-PP là tài sản có bản quyền của VGB**, không được chép vào
một sản phẩm bán đi. ReliaWind thì công bố công khai và là bộ de-facto
trong tài liệu nghiên cứu: một tổng quan 2025 trên ~48.600 tua-bin và 12
cơ sở dữ liệu vẫn dựng trên ReliaWind.

Nên gói này ship cây ReliaWind và **chừa sẵn cột ``rdspp_code``** cho
khách nào có giấy phép RDS-PP tự điền.

Ba điều bắt buộc của bảng master
--------------------------------
* **Tên gọi khác.** Cùng một cụm mang tên khác nhau tuỳ nguồn. Không khai
  thì nhập dữ liệu từ hai OEM sẽ đẻ ra hai loại trùng nghĩa.
* **Rổ "Khác".** Không có thì người nhập nhét bừa vào loại gần nhất.
* **Cây theo NỀN TẢNG.** Máy truyền động trực tiếp KHÔNG có hộp số. Cứng
  hoá hộp số vào mọi tua-bin là sai ngay từ dòng đầu.

Số liệu xếp hạng trong gói là GIÁ TRỊ THAM CHIẾU
------------------------------------------------
Thứ hạng hỏng hóc kèm theo chỉ để gợi ý mức quan trọng ban đầu. Mức quan
trọng thật phải suy ra từ lịch sử của CHÍNH đội máy đó: bộ dữ liệu CIRCE
(Tây Ban Nha, ~4.300 máy) cho thấy hệ ĐIỆN đứng đầu cả hai trục với máy
DFIG, ngược hẳn giả định phổ biến rằng hộp số thống trị.
""",
    'author': 'BSD Insight',
    'website': 'https://bsdinsight.com',
    'license': 'AGPL-3',
    'depends': ['eam_core'],
    'data': [
        'views/eam_wind_category_views.xml',
        'data/eam_wind_category_data.xml',
        'data/eam_wind_time_category_data.xml',
    ],
    'installable': True,
}
