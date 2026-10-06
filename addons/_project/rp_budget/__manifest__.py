# -*- coding: utf-8 -*-
{
    "name": "Realty Project — Ngân sách 3 lớp",
    "version": "19.0.2.0.0",
    "category": "Realty/Project",
    "summary": "Ngân sách gốc (đóng băng) → hiện hành → dự báo, và cảnh "
               "báo khi ngân sách tính động trôi khỏi mốc đã duyệt.",
    "description": """
Ngân sách 3 lớp (rp_budget)
===========================

`total_bac` của dự án là con số **tính động** từ BOQ: sửa một dòng BOQ
là nó đổi, và không để lại dấu vết. Hệ quả: không bao giờ trả lời được
câu hỏi quan trọng nhất của kiểm soát chi phí — *"so với lúc phê duyệt
đầu tư, ta đang vượt bao nhiêu"* — vì mẫu số tự trôi theo tử số.

Lịch thi công đã có baseline từ lâu; chi phí thì chưa. Module này bù
đúng chỗ đó, theo thông lệ kiểm soát chi phí EPC:

**Lớp 1 — Ngân sách gốc.** Một MỐC đóng băng: chụp lại từng khoản cấu
thành BAC tại thời điểm chốt, kèm người chốt và ngày chốt. Chụp cả
mã và tên dưới dạng chữ, nên xoá hay đổi tên gói thầu về sau cũng không
làm hỏng mốc cũ.

**Lớp 2 — Ngân sách hiện hành** = gốc + phát sinh ĐÃ DUYỆT. Đây là số
tiền thực sự được phép tiêu tại thời điểm này.

**Lớp 3 — Dự báo cuối kỳ** = đã cam kết theo hợp đồng + phát sinh đã
duyệt chưa vào hợp đồng + phát sinh đang chờ (lấy thẳng
`cost_forecast_total` của sổ phát sinh, không tính lại).

Và một chỉ số không có trong sách vở nhưng rất cần ngoài đời: **độ trôi
ngân sách** = BAC tính động − ngân sách gốc. Khác 0 nghĩa là có người
sửa BOQ sau khi đã chốt mốc mà chưa qua phát sinh. Đây là chỗ rò rỉ
âm thầm nhất của kiểm soát chi phí.

Chốt mốc mới KHÔNG xoá mốc cũ: mốc cũ chuyển sang "đã thay thế" và nằm
lại làm lịch sử.
    """,
    "author": "BSDInsight",
    "website": "https://bsdinsight.com",
    "license": "AGPL-3",
    "depends": [
        "rp_evm",
        "rp_variation",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_sequence.xml",
        "views/rp_cost_baseline_views.xml",
        "views/rp_contingency_drawdown_views.xml",
        "views/re_project_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
