# -*- coding: utf-8 -*-
"""Lõi hồ sơ giải ngân chuyển sang module re_loan_dossier.

Hai view dưới đây nay do module lõi khai. Không dọn trước khi nâng cấp
thì trong cùng một lượt, bản CŨ của rp_loan_bridge và bản MỚI của
re_loan_dossier cùng chèn tab "Hồ sơ giải ngân" vào form giải ngân —
ra hai tab trùng nhau.

Nhưng KHÔNG xoá thẳng được: module khác (tạm ứng) đang kế thừa hai view
này, Postgres chặn vì khoá ngoại. Trỏ view con sang view mới cũng
KHÔNG được: Odoo xác thực view con ngay lúc module lõi nạp, trong khi
trường của module con (advance_payment_id) chưa có trong registry —
module đó nạp sau. Cả hai cách đều đã thử và đều vỡ trên bản sao DB
demo.

Nên: XOÁ luôn cả view con. Module chủ của chúng đã sửa XML để khai vào
module lõi và đã tăng phiên bản, nên Odoo dựng lại chúng ngay trong
cùng lượt nâng cấp này.

Dữ liệu hồ sơ KHÔNG đụng tới: model giữ nguyên tên, bảng giữ nguyên.
"""
from odoo import SUPERUSER_ID, api

# (view cũ của rp_loan_bridge, view mới của re_loan_dossier)
MOVED_VIEWS = [
    ('rp_loan_bridge.view_rp_loan_disbursement_dossier_form',
     're_loan_dossier.view_rp_loan_disbursement_dossier_form'),
    ('rp_loan_bridge.view_re_loan_note_disbursement_form_inherit_dossier',
     're_loan_dossier.view_re_loan_note_disbursement_form_inherit_dossier'),
]


def _unlink_tree(view):
    """Xoá từ lá lên: view cháu tham chiếu view con, xoá con trước là
    Postgres chặn."""
    for child in view.inherit_children_ids:
        _unlink_tree(child)
    view.unlink()


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    for old_xmlid, _new_xmlid in MOVED_VIEWS:
        old = env.ref(old_xmlid, raise_if_not_found=False)
        if old:
            _unlink_tree(old)
