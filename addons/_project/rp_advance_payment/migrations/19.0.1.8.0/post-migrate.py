# -*- coding: utf-8 -*-
"""Hồ sơ giải ngân đã gắn phiếu Tạm ứng thì mang loại "Tạm ứng".

Phần lõi vừa có trục "Loại hồ sơ" (Hoá đơn / Tạm ứng) để khách không
dùng bộ Thi công vẫn khai được tạm ứng. Dữ liệu cũ nhận giá trị mặc
định 'invoice', mà hồ sơ tạm ứng thì không bao giờ có hoá đơn — để
nguyên là phép kiểm lúc gửi ngân hàng sẽ đòi hoá đơn của chính những
hồ sơ không thể có hoá đơn.
"""


def migrate(cr, version):
    cr.execute("""
        UPDATE rp_loan_disbursement_dossier
           SET dossier_kind = 'advance'
         WHERE advance_payment_id IS NOT NULL
           AND (dossier_kind IS NULL OR dossier_kind = 'invoice')
    """)
