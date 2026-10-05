# -*- coding: utf-8 -*-
{
    'name': 'Realty Project — Sổ hồ sơ kỹ thuật (điều 5.2)',
    'version': '19.0.1.0.0',
    'category': 'Realty/Project',
    'summary': 'Hồ sơ nhà thầu phải trình: đồng hồ xem xét 21 ngày, chuỗi '
               'lần trình, và cổng cho phép khởi công / bàn giao.',
    'description': """
Realty Project — Sổ hồ sơ kỹ thuật (rp_document)
================================================

Điều 5.2 của hợp đồng thiết kế–thi công không nói về việc lưu trữ file.
Nó là một **cơ chế thời hạn**, và ba câu trong đó quyết định ai được làm
gì khi nào:

* *"each review period shall not exceed 21 days, calculated from the date
  on which the Engineer receives a Contractor's Document and the
  Contractor's notice"* — đồng hồ chỉ chạy khi nhận được **cả hồ sơ lẫn
  thông báo** kèm theo. Nhà thầu gửi bản vẽ mà không kèm thông báo "hồ sơ
  đã sẵn sàng để xem xét" thì hạn chưa bắt đầu đếm, và sau này không lấy
  đó làm căn cứ đòi gia hạn được. Sổ này tách hai ngày đó ra, vì đây là
  chỗ hai bên hay đếm từ hai mốc khác nhau.
* *"execution shall not commence until the Engineer has approved"* — hồ
  sơ trình để **phê duyệt** thì chưa duyệt là chưa được thi công.
* *"shall not commence prior to the expiry of the review periods"* — hồ
  sơ trình để **xem xét** thì dù không ai trả lời cũng phải chờ hết hạn
  mới được làm, và làm thì tự chịu rủi ro.

Vì vậy mỗi hồ sơ mang một **CỔNG**: ngày sớm nhất mà phần việc dựa vào nó
được phép khởi công. Khai công việc phụ thuộc hồ sơ thì lịch thi công tự
biết việc nào đang chờ, chờ ai, và chờ bao nhiêu ngày — con số
*"việc chưa được phép khởi công"* không nằm trong tiến độ (Gantt vẫn
xanh), không nằm trong chi phí, và không ai báo cáo, cho tới lúc đã trễ.

Hai điều khoản con chặn **bàn giao** chứ không chặn khởi công: điều 5.6
(hồ sơ hoàn công) và 5.7 (tài liệu vận hành & bảo trì) — *"The Works
shall not be considered to be completed for the purposes of taking over …
until the Engineer has received"* chúng. Hiện trường xong mà hồ sơ thiếu
thì ngày bàn giao vẫn chưa chạy, và phạt chậm vẫn đếm.

Những thứ còn lại chỉ là hệ quả của ba điều trên:

* **Chuỗi lần trình** (Rev 0, 1, 2…) với kết quả A/B/C/D và số ngày thực
  tế đã xem xét từng lần. Bị trả lại rồi trình lại thì chi phí làm lại là
  của nhà thầu — nên phải đếm.
* **Phiếu chuyển hồ sơ**: ngoài hiện trường hồ sơ không đi lẻ, một công
  văn kèm mười hai bản vẽ và cả lô chạy hạn từ cùng một ngày. Ghi một
  phiếu là xong cả lô.
* **Quá hạn xem xét ra khiếu nại một nút**: quá hạn là lỗi bên chủ đầu
  tư, và công việc liên quan vẫn không được khởi công trong lúc chờ — nên
  số ngày quá hạn chính là số ngày nhà thầu xin gia hạn (rp_claim).
* **Bộ hồ sơ khởi tạo** theo điều 5.2/5.6/5.7 cho hợp đồng chưa có ma
  trận hồ sơ riêng — tạo rồi sửa theo Annex 16, nhanh hơn gõ từ đầu.
""",
    'author': 'BSDInsight',
    'website': 'https://bsdinsight.com',
    'license': 'LGPL-3',
    'depends': [
        'rp_contract',
        'rp_schedule',
        'rp_claim',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_sequence.xml',
        'views/rp_document_views.xml',
        'views/rp_transmittal_views.xml',
        'views/project_task_views.xml',
        'views/rp_contract_views.xml',
        'views/re_project_views.xml',
        'views/rp_document_menus.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
