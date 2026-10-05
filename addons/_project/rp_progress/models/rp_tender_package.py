# -*- coding: utf-8 -*-
"""Ngân sách gói thầu = Σ các dòng BOQ của chính gói đó.

Với hợp đồng trọn gói, đơn vị nhỏ nhất mà chủ đầu tư thật sự CAM KẾT
tiền và ĐO được tiền ra là GÓI THẦU, không phải hạng mục: nhà thầu
không báo tiền theo hạng mục, và theo Schedule 14.4 chủ đầu tư trả theo
phần trăm mốc thanh toán chứ không theo khối lượng.

Nên BOQ của chủ đầu tư treo ở gói thầu, và tổng của nó là ngân sách gói
— con số đem so với giá bỏ thầu, rồi so với giá hợp đồng hiện hành.
"""
from odoo import _, api, fields, models


class RpTenderPackage(models.Model):
    _inherit = 'rp.tender.package'

    boq_line_ids = fields.One2many(
        'rp.boq.line', 'package_id', string='BOQ ngân sách gói')
    boq_line_count = fields.Integer(
        string='Số dòng BOQ', compute='_compute_boq_budget')
    budget_amount = fields.Monetary(
        string='Ngân sách gói', compute='_compute_boq_budget', store=True,
        currency_field='currency_id',
        help='Tổng các dòng BOQ CÓ GIÁ và thuộc phương án đã chọn. Dòng '
             '"đã gộp vào mục khác" hay "ngoài phạm vi" không cộng.')
    budget_vs_contract = fields.Monetary(
        string='Chênh hợp đồng so ngân sách', compute='_compute_boq_budget',
        currency_field='currency_id',
        help='Giá hợp đồng hiện hành trừ ngân sách gói. Dương là đang '
             'vượt ngân sách đã duyệt cho gói này.')
    contract_value_total_pkg = fields.Monetary(
        string='Giá hợp đồng của gói', compute='_compute_boq_budget',
        currency_field='currency_id')

    @api.depends('boq_line_ids.amount', 'boq_line_ids.line_status',
                 'boq_line_ids.is_selected')
    def _compute_boq_budget(self):
        Contract = self.env['rp.contract']
        for pkg in self:
            lines = pkg.boq_line_ids
            pkg.boq_line_count = len(lines)
            pkg.budget_amount = sum(lines.mapped('amount'))
            gia = sum(Contract.search(
                [('tender_package_id', '=', pkg.id)]
            ).mapped('contract_value_pretax')) if pkg.id else 0.0
            pkg.contract_value_total_pkg = gia
            pkg.budget_vs_contract = gia - pkg.budget_amount
        # BAC của dự án là trường tính-và-lưu, mà Odoo không lần được
        # phụ thuộc từ gói thầu sang dự án (không có one2many nối hai
        # bên). Đổi ngân sách gói thì phải xếp lại hàng đợi tính BAC,
        # nếu không con số trên form dự án đứng im.
        du_an = self.mapped('project_id')
        if du_an:
            Proj = self.env['re.project']
            for ten in ('total_bac', 'project_eac', 'project_vac',
                        'cost_status'):
                if ten in Proj._fields:
                    self.env.add_to_compute(Proj._fields[ten], du_an)

    def action_open_boq(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('BOQ ngân sách — %s', self.name),
            'res_model': 'rp.boq.line',
            'view_mode': 'list,form',
            'views': [
                (self.env.ref(
                    'rp_progress.view_rp_boq_line_package_list').id, 'list'),
                (self.env.ref(
                    'rp_progress.view_rp_boq_line_form').id, 'form'),
            ],
            'domain': [('package_id', '=', self.id)],
            'context': {'default_package_id': self.id,
                        'default_uom_id': self.env[
                            'rp.progress.uom'].search(
                                [('name', 'ilike', 'Trọn gói')], limit=1).id},
        }
