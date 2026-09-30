# -*- coding: utf-8 -*-
"""Bridge: thêm nhóm chi phí / HĐ nhà thầu / hạng mục cho giải ngân.

Danh sách hồ sơ giải ngân và điều kiện gửi NH nằm ở `re_loan_dossier`
(lõi, không phụ thuộc bộ Thi công).
"""
from odoo import fields, models


class ReLoanNoteDisbursement(models.Model):
    _inherit = 're.loan.note.disbursement'

    cost_category_id = fields.Many2one(
        'rp.cost.category', string='Nhóm chi phí',
        domain="[('project_id', '=', project_id)]",
        help='Loại chi phí của khoản chi (rp.cost.category của dự án).')
    contract_id = fields.Many2one(
        'rp.contract', string='HĐ nhà thầu',
        domain="[('project_id', '=', project_id)]",
        help='HĐ nhà thầu được thanh toán bằng khoản giải ngân này '
             '(nếu giải ngân để trả nhà thầu).')
    structure_id = fields.Many2one(
        'rp.structure', string='Hạng mục',
        domain="[('project_id', '=', project_id)]",
        help='Hạng mục công trình (nếu cần theo dõi chi tiết hơn).')
