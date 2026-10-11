# -*- coding: utf-8 -*-
"""Điền loại tiền cho những dự án đang để trống.

``re_project.currency_id`` trước đây là trường tính-có-lưu, readonly, hàm
tính tự tham chiếu chính nó và không khai @api.depends — nên nó chỉ chạy
lúc tạo bản ghi và không bao giờ chạy lại. Dự án tạo TRƯỚC khi cài rp_evm
vì thế giữ cột NULL mãi, và bảng điều khiển EVM rơi về tiền tệ công ty:
nó dán ký hiệu ₫ lên những con số vốn là USD.

Nay trường đã là trường thường ghi được, nhưng bản ghi cũ vẫn NULL nên
phải điền một lần. Điền bằng tiền tệ của ĐÚNG công ty sở hữu dự án, chứ
không phải công ty đầu tiên trong bảng — cơ sở dữ liệu nhiều công ty thì
hai thứ đó khác nhau.

Lưu ý: chỉ điền chỗ NULL. Dự án nào đã có loại tiền thì giữ nguyên, kể cả
khi nó khác tiền tệ công ty — đó có thể là lựa chọn đúng của người dùng
(dự án ở nước ngoài ký hợp đồng bằng ngoại tệ).
"""


def migrate(cr, version):
    if not version:
        return

    # `re.project` KHÔNG chắc có company_id — ở bản hiện tại nó không có
    # cột này, nên câu lệnh join res_company sẽ nổ UndefinedColumn và làm
    # đổ cả lượt nâng cấp. Dò cột trước rồi mới chọn câu lệnh.
    cr.execute("""
        SELECT 1 FROM information_schema.columns
         WHERE table_name = 're_project' AND column_name = 'company_id'
    """)
    co_company = bool(cr.fetchone())

    theo_cong_ty = 0
    if co_company:
        cr.execute("""
            UPDATE re_project p
               SET currency_id = c.currency_id
              FROM res_company c
             WHERE p.company_id = c.id
               AND p.currency_id IS NULL
        """)
        theo_cong_ty = cr.rowcount

    # Dự án chưa gán công ty, hoặc cơ sở dữ liệu không có cột đó —
    # lấy tiền tệ của công ty gốc.
    cr.execute("""
        UPDATE re_project
           SET currency_id = (SELECT currency_id FROM res_company
                               ORDER BY id LIMIT 1)
         WHERE currency_id IS NULL
    """)
    con_lai = cr.rowcount

    if theo_cong_ty or con_lai:
        import logging
        logging.getLogger(__name__).info(
            'rp_evm: điền loại tiền cho %d dự án theo công ty sở hữu, '
            '%d dự án theo công ty gốc.', theo_cong_ty, con_lai)
