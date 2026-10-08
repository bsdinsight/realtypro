# -*- coding: utf-8 -*-
"""Tính lại ``energy_treatment`` sau khi trường đổi từ khai tay sang suy.

Bản 1.0.0 khai ``energy_treatment`` là trường thường với mặc định
``'loss'``. Bản này đổi nó thành trường tính-có-lưu.

Odoo **chỉ tính trường lưu cho những dòng có cột rỗng** tại lúc tạo cột.
Cột ở đây đã tồn tại và đã đầy giá trị ``'loss'``, nên hàm suy sẽ không
bao giờ chạy — mọi loại thời gian đứng nguyên ở "tổn thất thật", kể cả
cắt giảm do lưới. Không lỗi, không cảnh báo, chỉ là số sai.

Nên phải gọi thẳng hàm tính. Lưu ý không xoá cột về rỗng trước: trường
khai ``required=True`` nên cột mang ràng buộc NOT NULL, một câu
``UPDATE ... SET energy_treatment = NULL`` sẽ làm vỡ cả lần nâng cấp.
Gọi trực tiếp thì hàm tính ghi đè giá trị cũ, không cần dọn trước.
"""
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    C = env['eam.time.category']
    tat = C.with_context(active_test=False).search([])
    tat._compute_energy_treatment()
    tat.flush_recordset(['energy_treatment'])
    # Tiền trên sổ dừng máy phụ thuộc cách tính tiền, nên cũng phải tính
    # lại — nếu không thì khoảng bị lưới cắt giảm vẫn mang số lỗ cũ.
    O = env.get('eam.outage')
    if O is not None:
        ds = O.search([])
        ds._compute_tien()
        ds.flush_recordset(['energy_value', 'revenue_deemed', 'lost_revenue',
                            'tariff_applied'])
