# -*- coding: utf-8 -*-
"""
Phân bổ vay theo công trình (rp.loan.allocation).

Một dòng phân bổ gắn 1 Khế ước (re.loan.note) với 1 hoặc nhiều đích trong
chuỗi Realty Project:

  re.project → rp.structure → rp.cost.category → rp.tender.package → rp.contract

Phân bổ cái gì: principal (gốc) / interest (lãi) / both.
Phương pháp: percent (% của base amount) hoặc amount (số tiền tuyệt đối).
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


ALLOCATION_BASE = [
    ('principal', 'Gốc vay'),
    ('interest', 'Lãi vay'),
    ('both', 'Cả gốc + lãi'),
]


class RpLoanAllocation(models.Model):
    _name = 'rp.loan.allocation'
    _description = 'Phân bổ vay theo công trình'
    _order = 'note_id, sequence, id'

    sequence = fields.Integer(default=10)
    note_id = fields.Many2one(
        're.loan.note', string='Khế ước', required=True, ondelete='cascade',
        index=True)
    allowed_project_ids = fields.Many2many(
        're.project', string='Dự án cho phép',
        compute='_compute_allowed_project_ids',
        help='Tập dự án có phân bổ hạn mức trong HĐTD của KW. Filter '
             'project_id dropdown chỉ hiện các dự án này.')
    project_id = fields.Many2one(
        're.project', string='Dự án', required=True, ondelete='restrict',
        index=True,
        domain="[('id', 'in', allowed_project_ids)]")
    structure_id = fields.Many2one(
        'rp.structure', string='Hạng mục',
        domain="[('project_id','=',project_id)]",
        help='Hạng mục công trình (rp.structure). Để trống nếu phân bổ '
             'cấp dự án.')
    cost_category_id = fields.Many2one(
        'rp.cost.category', string='Nhóm chi phí',
        domain="[('project_id','=',project_id)]",
        help='Vd "9.1 Lãi vay capitalized trong xây dựng".')
    tender_package_id = fields.Many2one(
        'rp.tender.package', string='Gói thầu',
        domain="[('project_id','=',project_id)]")
    contract_id = fields.Many2one(
        'rp.contract', string='HĐ nhà thầu',
        domain="[('project_id','=',project_id)]")

    base = fields.Selection(
        ALLOCATION_BASE, string='Phân bổ', default='interest', required=True,
        help='Phân bổ gốc, lãi, hay cả hai. Lãi vay thường vào cost cat '
             '9.1 (capitalize).')
    method = fields.Selection(
        [('percent', 'Theo %'),
         ('amount', 'Số tiền tuyệt đối')],
        string='Phương pháp', default='percent', required=True)
    percent = fields.Float(string='%', digits=(5, 2))
    amount = fields.Monetary(string='Số tiền')
    amount_allocated = fields.Monetary(
        string='Số tiền phân bổ', compute='_compute_amount_allocated',
        store=True,
        help='Kết quả phân bổ thực tế: theo % hoặc số tiền nhập trực tiếp.')
    description = fields.Char(string='Diễn giải')

    currency_id = fields.Many2one(
        related='note_id.currency_id', store=True, readonly=True)
    company_id = fields.Many2one(
        related='note_id.company_id', store=True, readonly=True)

    # ----- Helpers --------------------------------------------------------
    def _base_amount(self):
        """Trả về số tiền cơ sở để tính % theo `base`."""
        self.ensure_one()
        note = self.note_id
        if self.base == 'principal':
            return note.amount
        if self.base == 'interest':
            return note.interest_total_planned
        return note.amount + note.interest_total_planned  # both

    # ----- Compute --------------------------------------------------------
    @api.depends('note_id',
                 'note_id.credit_contract_id.facility_ids.'
                 'project_allocation_ids.project_id')
    def _compute_allowed_project_ids(self):
        for rec in self:
            contract = rec.note_id.credit_contract_id
            if not contract:
                rec.allowed_project_ids = False
                continue
            project_ids = contract.facility_ids.mapped(
                'project_allocation_ids.project_id')
            rec.allowed_project_ids = project_ids

    @api.depends('method', 'percent', 'amount', 'base',
                 'note_id.amount', 'note_id.interest_total_planned')
    def _compute_amount_allocated(self):
        for rec in self:
            if rec.method == 'percent':
                rec.amount_allocated = (
                    rec._base_amount() * (rec.percent or 0.0) / 100.0)
            else:
                rec.amount_allocated = rec.amount or 0.0

    # ----- Onchange (UX) -------------------------------------------------
    @api.onchange('contract_id')
    def _onchange_contract_id(self):
        if self.contract_id:
            self.tender_package_id = self.contract_id.tender_package_id
            if not self.project_id:
                self.project_id = self.contract_id.project_id

    @api.onchange('tender_package_id')
    def _onchange_tender_package_id(self):
        if self.tender_package_id and not self.project_id:
            self.project_id = self.tender_package_id.project_id

    @api.onchange('structure_id')
    def _onchange_structure_id(self):
        if self.structure_id and not self.project_id:
            self.project_id = self.structure_id.project_id

    # ----- Constraints ---------------------------------------------------
    @api.constrains('percent', 'amount', 'method')
    def _check_values(self):
        for rec in self:
            if rec.method == 'percent':
                if rec.percent < 0 or rec.percent > 100:
                    raise ValidationError(_(
                        "% phân bổ phải trong 0–100."))
            else:
                if rec.amount < 0:
                    raise ValidationError(_(
                        "Số tiền phân bổ không được âm."))

    @api.constrains('structure_id', 'project_id')
    def _check_structure_project(self):
        for rec in self:
            if rec.structure_id \
                    and rec.structure_id.project_id != rec.project_id:
                raise ValidationError(_(
                    "Hạng mục phải thuộc dự án đã chọn."))

    @api.constrains('cost_category_id', 'project_id')
    def _check_cost_category_project(self):
        for rec in self:
            if rec.cost_category_id \
                    and rec.cost_category_id.project_id != rec.project_id:
                raise ValidationError(_(
                    "Nhóm chi phí phải thuộc dự án đã chọn."))

    @api.constrains('contract_id', 'project_id')
    def _check_contract_project(self):
        for rec in self:
            if rec.contract_id \
                    and rec.contract_id.project_id != rec.project_id:
                raise ValidationError(_(
                    "HĐ nhà thầu phải thuộc dự án đã chọn."))
