# -*- coding: utf-8 -*-
"""Dự án nhìn xuống hợp đồng nhà thầu.

Cùng lý do với gói thầu: liên kết vốn chỉ có một chiều, muốn biết dự án
này đã ký bao nhiêu hợp đồng thì phải sang menu Hợp đồng rồi tự lọc.
"""
from odoo import _, api, fields, models


class ReProjectContract(models.Model):
    _inherit = 're.project'

    rp_contract_ids = fields.One2many(
        'rp.contract', 'project_id', string='Hợp đồng nhà thầu')
    rp_contract_count = fields.Integer(
        string='Số hợp đồng nhà thầu', compute='_compute_rp_contract',
        store=True)

    # Không cộng tổng giá trị đã ký ở đây: ``re.project`` không có trường
    # tiền tệ (rp_evm mới thêm ``currency_id``), nên một Monetary trỏ vào
    # nó sẽ làm vỡ lúc nạp registry trên mọi DB chưa cài rp_evm. Số tiền
    # đã có sẵn ở màn hình đối chiếu ngân sách.

    @api.depends('rp_contract_ids')
    def _compute_rp_contract(self):
        for p in self:
            p.rp_contract_count = len(p.rp_contract_ids)

    def action_mo_hop_dong_nha_thau(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Hợp đồng nhà thầu — %s', self.name),
            'res_model': 'rp.contract',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }
