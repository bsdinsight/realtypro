# -*- coding: utf-8 -*-
{
    'name': 'EAMOne — Sản lượng đa kỳ, đa nhà máy',
    'version': '19.0.1.0.0',
    'category': 'EAMOne',
    'summary': 'Sản lượng theo ngày / tuần / tháng / năm, một hay nhiều '
               'nhà máy, so với mục tiêu P50/P75/P90.',
    'description': """
EAMOne — Sản lượng đa kỳ, đa nhà máy
=====================================

Một bảng, nhiều nơi đọc
------------------------
Câu *"tháng này so tháng trước thế nào"* và câu *"ba nhà máy cộng lại
được bao nhiêu"* đều cần cộng hàng nghìn dòng ngày. Tính lúc mở màn
hình thì mỗi lần mở là một lần quét lại — và không lọc được, không xếp
hạng được, không xuất được.

Quan trọng hơn: **bản đồ và các màn tổng quan đọc lại chính bảng này**.
Mỗi nơi tự cộng lấy là mỗi nơi một con số cho cùng một tháng, và tới
lúc lệch thì không ai biết bên nào mới.

Cộng từ BẢNG TỔ MÁY, không đọc lại kho chuỗi thời gian
-------------------------------------------------------
Bảng tổ máy đã là nơi quyết định *"ngày này nhà máy phát bao nhiêu"*.
Đọc lại từ kho số đo là mở đường cho hai con số — và chúng sẽ lệch,
chỉ là lệch lúc nào.

Ngày thiếu KHÔNG cộng thành 0
------------------------------
Một kỳ thiếu ba ngày dữ liệu vẫn ra con số dương trông bình thường, chỉ
nhỏ hơn thật. Nên mỗi dòng mang theo **số ngày có số** và **số ngày
thiếu**, đặt ngay cạnh con số — người đọc tự biết nên tin tới đâu.

So với mục tiêu: chỉ làm khi CÓ mục tiêu
-----------------------------------------
Kỳ chưa khai mục tiêu thì cột so sánh để **trống kèm lý do**, không ghi
0%. *"Đạt 0% kế hoạch"* và *"chưa ai khai kế hoạch"* là hai chuyện khác
hẳn nhau, và chỉ một trong hai đáng báo động.

Kỳ tuần vắt qua hai tháng thì mục tiêu cộng **theo tỷ lệ ngày** của
từng tháng. Lấy trọn mục tiêu tháng là so một tuần với kế hoạch cả
tháng — ra "đạt 20%" và cả phòng hoảng vì một phép chia sai.

Lần ngược được
---------------
Mỗi dòng có nút mở thẳng **bảng tổ máy đúng kỳ đó**. Một con số tổng
mà không lần ngược được tới dòng chi tiết thì không ai dám mang nó ra
bàn họp.
""",
    'author': 'BSD Insight',
    'website': 'https://bsdinsight.com',
    'license': 'LGPL-3',
    'depends': ['eam_core', 'eam_unit_day', 'eam_target'],
    'data': [
        'security/ir.model.access.csv',
        'data/eam_energy_period_cron.xml',
        'views/eam_energy_period_views.xml',
    ],
    'installable': True,
}
