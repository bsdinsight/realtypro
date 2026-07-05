# -*- coding: utf-8 -*-
"""
Dòng khối lượng nghiệm thu của BBN KLCV.

1 dòng = 1 đầu việc trong BOQ (cost.category × structure). User nhập
quantity_this_period (KL kỳ này), hệ thống tự tính:
  - quantity_to_date_prev: lũy kế các BBN approved trước của cùng đầu
    việc (compute động)
  - quantity_to_date = prev + this
  - amount_this_period = quantity_this_period × unit_price
  - amount_to_date = quantity_to_date × unit_price
  - progress_percent = quantity_to_date / quantity_estimated × 100
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class RpProgressAcceptanceLine(models.Model):
    _name = 'rp.progress.acceptance.line'
    _description = 'Dòng nghiệm thu khối lượng BBN'
    _order = 'acceptance_id, sequence, id'

    acceptance_id = fields.Many2one(
        'rp.progress.acceptance', string='BBN',
        required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)

    # --- Tham chiếu Dự toán ---
    boq_line_id = fields.Many2one(
        'rp.boq.line', string='Dòng dự toán (BOQ)',
        domain="[('structure_id', 'in', contract_structure_ids)]",
        help='Chọn đầu việc từ Dự toán chi tiết (BOQ) → tự fill nhóm chi '
             'phí, hạng mục, ĐVT, đơn giá, KL dự toán. Nguồn baseline '
             'chuẩn để tính EV theo đầu việc.')
    estimate_line_id = fields.Many2one(
        'rp.structure.estimate.line', string='Dòng Khái toán',
        help='Legacy — Khái toán chỉ có nhóm chi phí + số tiền (không có '
             'KL/đơn giá). Ưu tiên dùng "Dòng dự toán (BOQ)" ở trên.')
    cost_category_id = fields.Many2one(
        'rp.cost.category', string='Nhóm chi phí',
        help='Optional — BBNT đơn giản không track theo nhóm chi phí '
             'có thể bỏ trống. Khi có thì dùng để tính lũy kế theo '
             'cost_category trong _compute_qty_prev.')
    # Auto-compute danh sách hạng mục thuộc gói thầu của HĐ — dùng
    # cho domain filter cột "Hạng mục" trên list view BBNT.
    contract_structure_ids = fields.Many2many(
        'rp.structure', compute='_compute_contract_structure_ids',
        string='Hạng mục trong gói thầu')
    structure_id = fields.Many2one(
        'rp.structure', string='Hạng mục',
        domain="[('id', 'in', contract_structure_ids)]",
        help='Hạng mục công trình mà khối lượng này thuộc về. '
             'Dropdown chỉ hiện hạng mục thuộc gói thầu của HĐ nhà '
             'thầu (qua tender_package_id.line_ids).')

    @api.depends(
        'contract_id',
        'contract_id.tender_package_id',
        'contract_id.tender_package_id.line_ids.structure_id',
        'acceptance_id.contract_id')
    def _compute_contract_structure_ids(self):
        for line in self:
            # 2 path: contract_id (related store) hoặc trực tiếp từ
            # acceptance_id (cho virtual records trong form dialog
            # khi acceptance chưa save → contract_id related chưa flush).
            contract = (
                line.contract_id
                or line.acceptance_id.contract_id)
            pkg = contract.tender_package_id if contract else False
            if pkg:
                line.contract_structure_ids = pkg.line_ids.mapped(
                    'structure_id')
            else:
                line.contract_structure_ids = False
    description = fields.Char(string='Diễn giải công việc')

    # --- Đơn vị tính + đơn giá ---
    uom_id = fields.Many2one(
        'rp.progress.uom', string='ĐVT', required=True)
    unit_price = fields.Monetary(
        string='Đơn giá', required=True,
        help='Đơn giá theo BOQ. Nếu BOQ đổi giữa kỳ phải qua phụ lục HĐ.')

    # --- Khối lượng ---
    quantity_estimated = fields.Float(
        string='KL dự toán', digits=(16, 3), default=0.0,
        help='Khối lượng theo BOQ. Optional — bỏ trống nếu BBNT đơn '
             'giản không track BOQ. Có thể adjust qua phụ lục HĐ. '
             'Nếu = 0 thì progress_percent của dòng = 0.')
    quantity_to_date_prev = fields.Float(
        string='KL lũy kế kỳ trước', digits=(16, 3),
        compute='_compute_qty_prev', store=True,
        help='Tổng khối lượng các BBN đã duyệt TRƯỚC BBN này, '
             'cùng cost_category × structure trong cùng HĐ.')
    quantity_this_period = fields.Float(
        string='KL kỳ này', digits=(16, 3), default=0.0,
        help='User nhập — khối lượng thi công của riêng kỳ này.')
    quantity_to_date = fields.Float(
        string='KL lũy kế đến kỳ', digits=(16, 3),
        compute='_compute_qty_to_date', store=True)

    # --- Tiền ---
    amount_this_period = fields.Monetary(
        string='Giá trị kỳ này',
        compute='_compute_amounts', store=True)
    amount_to_date = fields.Monetary(
        string='Giá trị lũy kế',
        compute='_compute_amounts', store=True)
    progress_percent = fields.Float(
        string='% hoàn thành',
        compute='_compute_progress_percent', store=True,
        help='= quantity_to_date / quantity_estimated × 100.')

    currency_id = fields.Many2one(
        related='acceptance_id.currency_id', store=True, readonly=True)
    company_id = fields.Many2one(
        related='acceptance_id.company_id', store=True, readonly=True)
    contract_id = fields.Many2one(
        related='acceptance_id.contract_id', store=True, readonly=True)
    state = fields.Selection(
        related='acceptance_id.state', store=True, readonly=True)

    # ------------------------------------------------------------------
    # Onchange: pre-fill từ BOQ line (nguồn chính) / estimate_line (legacy)
    # ------------------------------------------------------------------
    @api.onchange('boq_line_id')
    def _onchange_boq_line(self):
        if self.boq_line_id:
            boq = self.boq_line_id
            self.cost_category_id = boq.category_id
            self.structure_id = boq.structure_id
            self.description = boq.description or ''
            self.uom_id = boq.uom_id
            self.unit_price = boq.unit_price
            self.quantity_estimated = boq.quantity

    @api.onchange('estimate_line_id')
    def _onchange_estimate_line(self):
        if self.estimate_line_id:
            est = self.estimate_line_id
            self.cost_category_id = est.category_id
            self.structure_id = est.structure_id
            self.description = est.description or ''
            # uom + unit_price + quantity_estimated:
            # rp.structure.estimate.line schema phụ thuộc rp_estimate
            # — nếu fields không có sẽ giữ trống, user nhập tay.
            if hasattr(est, 'uom_id') and est.uom_id:
                # estimate dùng uom.uom (Odoo std) — không bắt buộc map
                pass
            if hasattr(est, 'unit_price'):
                self.unit_price = est.unit_price
            if hasattr(est, 'quantity'):
                self.quantity_estimated = est.quantity

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends('cost_category_id', 'structure_id',
                 'acceptance_id.contract_id', 'acceptance_id.state',
                 'acceptance_id.date_submitted')
    def _compute_qty_prev(self):
        for line in self:
            acc = line.acceptance_id
            if not acc.contract_id or not line.cost_category_id:
                line.quantity_to_date_prev = 0.0
                continue
            # Lấy các line của BBN ĐÃ DUYỆT trước BBN này, cùng HĐ +
            # cùng cost_category + cùng structure
            domain = [
                ('acceptance_id.contract_id', '=', acc.contract_id.id),
                ('acceptance_id.state', '=', 'approved'),
                ('cost_category_id', '=', line.cost_category_id.id),
                ('id', '!=', line.id),
            ]
            if line.structure_id:
                domain.append(
                    ('structure_id', '=', line.structure_id.id))
            else:
                domain.append(('structure_id', '=', False))
            # Lọc theo ngày: BBN approved có date_submitted ≤ acc.date_submitted
            if acc.date_submitted:
                domain.append(
                    ('acceptance_id.date_submitted', '<=',
                     acc.date_submitted))
            prev_lines = self.search(domain)
            line.quantity_to_date_prev = sum(
                prev_lines.mapped('quantity_this_period'))

    @api.depends('quantity_to_date_prev', 'quantity_this_period')
    def _compute_qty_to_date(self):
        for line in self:
            line.quantity_to_date = (
                line.quantity_to_date_prev + line.quantity_this_period)

    @api.depends('quantity_this_period', 'quantity_to_date', 'unit_price')
    def _compute_amounts(self):
        for line in self:
            line.amount_this_period = (
                line.quantity_this_period * line.unit_price)
            line.amount_to_date = line.quantity_to_date * line.unit_price

    @api.depends('quantity_to_date', 'quantity_estimated')
    def _compute_progress_percent(self):
        for line in self:
            if line.quantity_estimated:
                line.progress_percent = (
                    line.quantity_to_date / line.quantity_estimated
                    * 100.0)
            else:
                line.progress_percent = 0.0

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    @api.constrains('quantity_this_period', 'quantity_estimated',
                    'quantity_to_date_prev')
    def _check_quantities(self):
        for line in self:
            if line.quantity_this_period < 0:
                raise ValidationError(_(
                    "Khối lượng không được âm."))
            # KL dự toán optional — chỉ check overrun khi user có nhập
            if line.quantity_estimated > 0 and (
                    line.quantity_to_date >
                    line.quantity_estimated + 0.001):
                raise ValidationError(_(
                    "KL lũy kế (%(t)s) vượt KL dự toán (%(e)s) ở dòng "
                    "'%(d)s'. Cần phụ lục HĐ để điều chỉnh dự toán "
                    "trước khi nghiệm thu KL vượt.",
                    t=line.quantity_to_date,
                    e=line.quantity_estimated,
                    d=line.description or line.cost_category_id.name))
