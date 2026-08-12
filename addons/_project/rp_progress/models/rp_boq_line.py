# -*- coding: utf-8 -*-
"""rp.boq.line — Dự toán chi tiết (BOQ) per hạng mục.

Bill of Quantities: mỗi dòng = 1 đầu việc trong 1 hạng mục, gồm
khối lượng × đơn giá → thành tiền. Đây là lớp **Dự toán CHI TIẾT** bổ
sung cho **Khái toán** (rp.structure.estimate.line — chỉ số tiền tổng
theo nhóm chi phí).

Coexist với Khái toán (không thay thế):
- Giai đoạn đầu chưa có BOQ → BAC = Σ Khái toán (estimate_total).
- Khi đã nhập BOQ → BAC = Σ BOQ (structure.estimate_value ưu tiên
  boq_total). Xem rp_progress/models/rp_structure.py.

BOQ là baseline khối lượng để BBN Nghiệm thu
(rp.progress.acceptance.line) trỏ vào (Phase 1b) → EV tự khớp theo
từng đầu việc.

Đặt trong rp_progress (KHÔNG phải rp_cost_base) vì:
- cần rp.progress.uom (ĐVT xây dựng) vốn định nghĩa ở rp_progress;
- rp_cost_base là base, KHÔNG được depend rp_progress (tránh circular);
- BOQ ↔ BBN ↔ EVM engine (Phase P4) cùng sống ở rp_progress → cohesive.

Khác Khái toán: BOQ cho phép NHIỀU dòng cùng một nhóm chi phí trên một
hạng mục (mỗi đầu việc là 1 dòng riêng) → KHÔNG unique theo category.
"""
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class RpBoqLine(models.Model):
    _name = 'rp.boq.line'
    _description = 'Dòng dự toán chi tiết (BOQ)'
    _order = 'structure_id, category_sequence, sequence, id'

    # ----- Neo vào hạng mục (parent)
    structure_id = fields.Many2one(
        'rp.structure', string='Hạng mục',
        required=True, ondelete='cascade', index=True)
    project_id = fields.Many2one(
        related='structure_id.project_id', store=True, index=True)
    subzone_id = fields.Many2one(
        related='structure_id.subzone_id', store=True, index=True)
    structure_level = fields.Selection(
        related='structure_id.structure_level', store=True)
    currency_id = fields.Many2one(
        related='structure_id.currency_id', store=True)
    company_id = fields.Many2one(
        related='structure_id.company_id', store=True, index=True)

    # ----- Nhóm chi phí (cùng dự án với hạng mục)
    category_id = fields.Many2one(
        'rp.cost.category', string='Nhóm chi phí',
        required=True, ondelete='restrict', index=True,
        domain="[('project_id', '=', project_id)]",
        help='Nhóm chi phí từ cây nhóm của dự án; phải cùng dự án với '
             'hạng mục.')
    category_sequence = fields.Integer(
        related='category_id.sequence', store=True, index=True)

    # ----- Đầu việc + khối lượng × đơn giá
    cost_element = fields.Selection(
        [('material', 'Vật liệu'),
         ('labor', 'Nhân công'),
         ('machine', 'Máy thi công'),
         ('subcontract', 'Thầu phụ'),
         ('overhead', 'Chi phí chung'),
         ('other', 'Khác')],
        string='Yếu tố chi phí', index=True,
        help='Chiều thứ HAI của chi phí, độc lập với cây nhóm chi phí '
             '(vốn chia theo HẠNG MỤC CÔNG VIỆC). Để riêng thành trường '
             'thay vì nhánh trong cây — nếu nhét vào cây sẽ phải nhân '
             'chéo 10 nhóm × 5 yếu tố. Nhờ vậy xem theo hạng mục hay '
             'pivot theo yếu tố đều được.')
    sequence = fields.Integer(string='STT', default=10)
    description = fields.Char(
        string='Đầu việc', required=True, translate=True,
        help='Diễn giải đầu việc (vd "Đào đất móng", "Đổ bê tông cột").')
    uom_id = fields.Many2one(
        'rp.progress.uom', string='ĐVT', required=True,
        help='Đơn vị tính khối lượng (m³, m², tấn…). Dùng chung với BBN '
             'nghiệm thu.')
    quantity = fields.Float(
        string='Khối lượng', digits=(16, 3), default=0.0)
    unit_price = fields.Monetary(
        string='Đơn giá', currency_field='currency_id', default=0.0)
    amount = fields.Monetary(
        string='Thành tiền', currency_field='currency_id',
        compute='_compute_amount', store=True,
        help='= Khối lượng × Đơn giá.')
    note = fields.Text(string='Ghi chú')

    # ------------------------------------------------------------------
    # Compute
    # ------------------------------------------------------------------
    @api.depends('quantity', 'unit_price')
    def _compute_amount(self):
        for line in self:
            line.amount = (line.quantity or 0.0) * (line.unit_price or 0.0)

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------
    @api.constrains('category_id', 'structure_id')
    def _check_category_same_project(self):
        for line in self:
            if line.category_id.project_id != line.structure_id.project_id:
                raise ValidationError(
                    f'[{line.structure_id.display_name}] Nhóm chi phí '
                    f'"{line.category_id.display_name}" thuộc dự án khác. '
                    f'Nhóm chi phí phải cùng dự án với hạng mục.')

    @api.constrains('quantity', 'unit_price')
    def _check_non_negative(self):
        for line in self:
            if line.quantity < 0 or line.unit_price < 0:
                raise ValidationError(
                    f'Khối lượng và đơn giá không được âm '
                    f'(dòng "{line.description}" trên '
                    f'{line.structure_id.display_name}).')
