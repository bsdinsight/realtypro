# -*- coding: utf-8 -*-
{
    'name': 'EAMOne — Doanh thu tổn thất',
    'version': '19.0.1.0.1',
    'category': 'EAMOne',
    'summary': 'Nối sổ dừng máy vào kỳ sản lượng và giá PPA — ra tiền '
               'thật, và ra cả phần đòi được.',
    'description': """
Mẩu khép vòng tiền
==================

Trước module này, ``lost_mwh`` và ``lost_revenue`` trên sổ dừng máy phải
nhập tay. Sau module này, tiền tính từ **giá PPA thật của chính kỳ đó**.

::

    khoảng dừng → kỳ sản lượng → giá áp dụng của kỳ → giá trị sản lượng mất
                                                    → trừ phần được đền
                                                    → quy trách nhiệm → đòi ai

Ba chỗ dễ nối nhầm, và cả ba đều ra số sai mà vẫn trông hợp lý
--------------------------------------------------------------

**① Mốc đối chiếu.** ``rp.energy.period`` có ba con số nghe na ná:

* ``loss_mwh`` — tổn thất trên **đường dây** tới điểm giao. Thuần vật lý,
  không liên quan gì tới dừng máy.
* ``shortfall_mwh`` — phần hụt **dưới mức cam kết** khả dụng. Đây là số
  đi đòi nhà thầu, và nó chỉ là phần ngọn.
* ``unavail_mwh`` (module này thêm) — **toàn bộ** sản lượng mất vì máy
  không khả dụng. Đây mới là mẫu số để đối chiếu sổ dừng máy.

Khoảng cách giữa hai cái sau rất lớn. Một kỳ thật của dự án điện gió
187 MW: khả dụng 97,90% so với cam kết 98,00% cho ``shortfall_mwh``
46,9 MWh, trong khi tổn thất do không khả dụng là **985,3 MWh** —
lệch 21 lần. Cam kết 98% nghĩa là 2% dừng máy được phép xảy ra: mất sản
lượng mà không ai phải trả. Lấy ``shortfall_mwh`` làm mẫu số thì độ bao
phủ nhảy lên 348%, rồi người đọc sẽ "sửa" bằng cách bóp sổ dừng máy
xuống cho khớp — tức xoá dấu 94% lượng dừng máy thật.

**Đối chiếu theo ``unavail_mwh``, đòi tiền theo ``shortfall_mwh``.**

**② Không phải MWh mất nào cũng là tiền mất.** Lưới bắt giảm thì sản
lượng mất thật, nhưng điều khoản *deemed energy* của hợp đồng mua bán
điện vẫn trả — có hợp đồng trả đủ 100%. Cộng khoản đó vào tổn thất là
khai lỗ cho một khoản đã được đền. Và gió dưới ngưỡng khởi động thì
không mất gì cả, vì không có gì để lấy. Ba trường hợp này bị chuẩn gộp
chung vào ô "không phải thời gian dừng", nên module thêm trường
``energy_treatment``, suy sẵn trong Python và vẫn sửa được.

Giá trị này **không** khai bằng tệp dữ liệu, dù đó là cách tự nhiên nhất.
Gói ngành khai các loại thời gian với ``noupdate="1"``; cờ đó ghi vào
``ir_model_data`` và từ đó không module nào ghi đè các bản ghi ấy bằng
XML được nữa — Odoo bỏ qua **im lặng**, không lỗi, không cảnh báo. Tệp
dữ liệu ghi đè sẽ chạy trót lọt và không đổi gì cả.

**③ Số mất khác số đòi được.** Module cho ra ba con số RIÊNG và không
trộn: *thiệt hại kinh tế do bên thứ ba gây*, *trần đòi theo hợp đồng*
(giá trị phần dưới mức cam kết), và *số đòi được* = min của hai cái
trước. Ngay cả con số thứ ba vẫn là số để đi đàm phán: chế tài khả dụng
còn có công thức riêng, trần trách nhiệm theo năm, và thường loại trừ
giờ do lưới hoặc bất khả kháng khỏi mẫu số khả dụng.

Độ bao phủ — chỉ số đáng tin nhất của sổ
----------------------------------------
``outage_coverage_percent`` = MWh sổ dừng máy giải thích được, chia cho
tổn thất do không khả dụng.

Dưới 100% nghĩa là **có sản lượng mất mà không ai biết vì sao** — và
phần chênh được bày thẳng ra ở ``outage_unexplained_mwh``. Đó là con số
nên nhìn trước khi tin bất kỳ báo cáo khả dụng nào, kể cả của chính mình.
""",
    'author': 'BSD Insight',
    'website': 'https://bsdinsight.com',
    'license': 'AGPL-3',
    'depends': ['eam_core', 'eam_wind', 'rp_ppa'],
    'data': ['views/eam_energy_views.xml'],
    'installable': True,
}
