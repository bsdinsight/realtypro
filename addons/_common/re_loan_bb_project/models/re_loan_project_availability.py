# -*- coding: utf-8 -*-
"""Khả dụng theo dự án khi có bộ thi công: thêm trục HỢP ĐỒNG nhà thầu.

Lõi tính khả dụng theo DỰ ÁN và cố ý không khai phụ thuộc vào
`contract_id` — trường đó do rp_loan_bridge khai. Ở đây khai lại hàm
tính với danh sách phụ thuộc ĐẦY ĐỦ (gồm hợp đồng) để đổi hợp đồng trên
dòng phân bổ hay trên đợt giải ngân là số tự tính lại.

Thân hàm vẫn là của lõi — chỗ này chỉ mở rộng depends.
"""
from odoo import api, models


class ReLoanFacilityProjectAllocationContract(models.Model):
    _inherit = 're.loan.facility.project.allocation'

    @api.depends('facility_id', 'project_id', 'amount', 'contract_id',
                 'facility_id.note_ids.disbursement_ids.contract_id',
                 'facility_id.note_ids.principal_outstanding',
                 'facility_id.note_ids.state',
                 'facility_id.note_ids.project_id',
                 'facility_id.note_ids.disbursement_ids.project_id',
                 'facility_id.note_ids.disbursement_ids.amount',
                 'facility_id.note_ids.disbursement_ids.state',
                 'facility_id.facility_pledge_ids.base_contribution',
                 'facility_id.facility_pledge_ids.state')
    def _compute_project_numbers(self):
        return super()._compute_project_numbers()
