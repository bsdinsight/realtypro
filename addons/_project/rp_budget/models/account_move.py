# -*- coding: utf-8 -*-
"""Buộc EVM của dự án tính lại khi hoá đơn nhà thầu vào sổ / ra khỏi sổ.

`total_ac` là compute LƯU, và `@api.depends` của nó chỉ liệt kê
`structure_ids.*` + `project_cost_direct_total`. Hoá đơn của gói thầu
EPC không chạm vào trường nào trong danh sách đó, nên vào sổ xong AC
vẫn giữ số cũ — nhìn thì tưởng công thức sai, thực ra compute chưa hề
chạy lại.

Không thêm được vào `depends` vì chi phí theo gói là trường KHÔNG lưu
(nó phải truy ngược chuỗi hoá đơn → mốc → hợp đồng → gói). Nên đánh dấu
cần tính lại bằng tay, đúng cách `rp_tender_package` đang làm với BAC.
"""
from odoo import models

# Cùng một hàm compute, nhưng đánh dấu đủ cả nhóm cho chắc.
_TRUONG_EVM = ('total_ac', 'total_cv', 'project_cpi',
               'project_eac', 'project_vac')


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _rp_danh_dau_tinh_lai_evm(self):
        du_an = self.mapped(
            'payment_milestone_id.contract_id.project_id')
        if not du_an:
            return
        Project = self.env['re.project']
        for ten in _TRUONG_EVM:
            truong = Project._fields.get(ten)
            if truong:
                self.env.add_to_compute(truong, du_an)

    def _post(self, soft=True):
        res = super()._post(soft=soft)
        res._rp_danh_dau_tinh_lai_evm()
        return res

    def button_draft(self):
        res = super().button_draft()
        self._rp_danh_dau_tinh_lai_evm()
        return res
