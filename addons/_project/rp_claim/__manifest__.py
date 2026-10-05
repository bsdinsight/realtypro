# -*- coding: utf-8 -*-
{
    'name': 'Realty Project — Khiếu nại, gia hạn (EOT) & phạt chậm',
    'version': '19.0.1.0.0',
    'category': 'Realty/Project',
    'summary': 'Sổ khiếu nại hai chiều, đếm hạn thông báo, gia hạn ra '
               'phụ lục, và phạt chậm tính trên mốc đã gia hạn.',
    'description': """
Realty Project — Khiếu nại, gia hạn và phạt chậm (rp_claim)
===========================================================

Dự án trễ thì câu hỏi tiếp theo luôn là "lỗi của ai, ai trả tiền". Trả
lời được câu đó cần ba thứ gắn vào nhau mà bảng tính không giữ nổi.

**Sổ khiếu nại hai chiều.** Nhà thầu khiếu nại chủ đầu tư và chủ đầu tư
khiếu nại nhà thầu nằm chung một sổ, trên cùng một hợp đồng — có vậy mới
thấy "ai nợ ai". Khiếu nại trỏ được về gốc sự việc: một điểm bàn giao hỏng
trong sổ ranh giới gói thầu, hoặc các công việc bị ảnh hưởng trong lịch thi công.

**Đếm hạn thông báo.** Hợp đồng xây dựng nào cũng có điều khoản thời hạn
thông báo (mặc định 28 ngày); quá hạn là mất quyền khiếu nại dù lý do
đúng. Hệ thống tính hạn chót từ ngày sự kiện, và cảnh báo đỏ ngay trên
hồ sơ khi thông báo gửi muộn. Đây là chỗ nhà thầu mất tiền nhiều nhất và
chủ đầu tư hay quên đếm.

**Gia hạn phải ra phụ lục.** Khiếu nại EOT được chấp thuận thì bấm một
nút để lập phụ lục hợp đồng loại "gia hạn" với ngày hoàn thành mới. Gia
hạn chỉ nằm trong sổ khiếu nại thì không có giá trị pháp lý, và quan
trọng hơn: không dời được mốc tính phạt.

**Phạt chậm tính trên mốc ĐÃ GIA HẠN.** `date_end + tổng ngày gia hạn
đã chấp thuận` mới là mốc để đếm ngày chậm; ngày về đích lấy từ lịch thi
công của chính hợp đồng. Tiền phạt = số ngày × mức phạt × giá trị căn
cứ, có áp trần theo hợp đồng. Con số trên form hợp đồng là DỰ BÁO và đổi
theo lịch; khi cần chốt thì lập **biên bản tính phạt** — số liệu được
đóng băng kèm ngày chốt, mốc hợp đồng, số ngày gia hạn và cách tính.
""",
    'author': 'BSDInsight',
    'website': 'https://bsdinsight.com',
    'license': 'LGPL-3',
    'depends': [
        'rp_contract',
        'rp_schedule',
        'rp_interface',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_sequence.xml',
        'views/rp_claim_views.xml',
        'views/rp_contract_views.xml',
        'views/rp_claim_menus.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
