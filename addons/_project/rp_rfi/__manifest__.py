# -*- coding: utf-8 -*-
{
    'name': 'Realty Project — RFI & Trình duyệt',
    'version': '19.0.1.0.0',
    'category': 'Realty/Project',
    'summary': 'RFI (yêu cầu làm rõ), Chỉ thị công trường (Site '
               'Instruction), Trình duyệt mẫu vật liệu/shopdrawing '
               '(Submittal) — 3 luồng hỏi–đáp–chỉ đạo chính thức.',
    'description': """
Realty Project — RFI & Trình duyệt (rp_rfi)
===========================================

Ba luồng văn bản chính thức giữa Nhà thầu ↔ TVGS/Thiết kế/CĐT:

1. **RFI — Phiếu yêu cầu làm rõ**: nhà thầu hỏi khi vướng bản vẽ /
   xung đột thiết kế / thiếu thông tin. Có hạn trả lời + đồng hồ đếm
   ngày chờ (RFI trễ = căn cứ claim tiến độ), cờ ảnh hưởng chi phí /
   tiến độ, chuỗi hỏi–đáp có giá trị hồ sơ.
2. **Chỉ thị công trường (SI)**: chiều ngược lại — CĐT/TVGS ra chỉ
   thị cho nhà thầu; cờ phát sinh chi phí; nhà thầu xác nhận thực
   hiện kèm ảnh; nghiệm thu đóng chỉ thị.
3. **Trình duyệt (Submittal)**: nhà thầu trình mẫu vật liệu / bản vẽ
   chế tạo / biện pháp thi công → duyệt / duyệt có điều kiện / từ
   chối (trình lại, đếm số lần revision).

Neo vào xương sống dự án: dự án → hạng mục → HĐ nhà thầu; smart
button trên HĐ (RFI mở, chỉ thị chưa xong, trình duyệt chờ).
""",
    'author': 'BSDInsight',
    'website': 'https://bsdinsight.com',
    'license': 'LGPL-3',
    'depends': [
        'mail',
        'rp_contract',
        'rp_cost_base',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'views/rp_rfi_views.xml',
        'views/rp_site_instruction_views.xml',
        'views/rp_submittal_views.xml',
        'views/rp_contract_views.xml',
        'views/rp_rfi_menus.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
