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
    _order = 'package_id, structure_id, sequence, id'

    # ----- Neo vào HẠNG MỤC hoặc GÓI THẦU (một trong hai)
    #
    # Hai lối dùng khác nhau, cùng một hình thù dữ liệu:
    #  · neo HẠNG MỤC — chủ đầu tư tự làm, đo theo khối lượng, BOQ là
    #    baseline để biên bản nghiệm thu trỏ vào;
    #  · neo GÓI THẦU — mua trọn gói EPC. BOQ là bảng giá của chủ đầu tư
    #    theo đầu mục, dùng làm NGÂN SÁCH GÓI và để so từng dòng với giá
    #    nhà thầu bỏ. Khối lượng thường là "1 trọn gói".
    structure_id = fields.Many2one(
        'rp.structure', string='Hạng mục',
        ondelete='cascade', index=True)
    package_id = fields.Many2one(
        'rp.tender.package', string='Gói thầu',
        ondelete='cascade', index=True)
    project_id = fields.Many2one(
        're.project', string='Dự án', compute='_compute_anchor',
        store=True, index=True)
    subzone_id = fields.Many2one(
        're.subzone', compute='_compute_anchor', store=True, index=True)
    structure_level = fields.Selection(
        related='structure_id.structure_level', store=True)
    currency_id = fields.Many2one(
        'res.currency', compute='_compute_anchor', store=True)
    company_id = fields.Many2one(
        'res.company', compute='_compute_anchor', store=True, index=True)

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
    # BOQ thật của chủ đầu tư có dòng KHÔNG mang tiền, và lý do khác
    # nhau hẳn: "đã gộp vào mục khác" ≠ "nằm ngoài phạm vi". Để tiền = 0
    # thì lúc so với giá nhà thầu sẽ tưởng là bỏ sót.
    line_status = fields.Selection(
        [('priced', 'Có giá'),
         ('included', 'Đã gộp vào mục khác'),
         ('excluded', 'Ngoài phạm vi')],
        string='Tình trạng', default='priced', required=True, index=True)
    # Một đầu mục có thể có nhiều phương án (BOP: cáp trên không hay cáp
    # ngầm). Chỉ phương án được CHỌN mới vào ngân sách gói — chênh lệch
    # giữa hai phương án chính là nguồn của khoản phát sinh về sau.
    option_code = fields.Char(
        string='Phương án',
        help='Để trống nếu đầu mục chỉ có một phương án.')
    is_selected = fields.Boolean(
        string='Phương án đã chọn', default=True, index=True)

    # BOQ gói thiết bị tách tiền MUA SẮM và tiền XÂY LẮP trên cùng một
    # dòng (gói HV: cung cấp 7,33 triệu + lắp đặt 4,10 triệu). Khai hai
    # cột thì thành tiền lấy tổng hai cột, bỏ trống thì quay về
    # khối lượng × đơn giá.
    amount_supply = fields.Monetary(
        string='Cung cấp / mua sắm', currency_field='currency_id')
    amount_install = fields.Monetary(
        string='Xây lắp', currency_field='currency_id')
    amount = fields.Monetary(
        string='Thành tiền', currency_field='currency_id',
        compute='_compute_amount', store=True,
        help='Có khai cung cấp/xây lắp thì = tổng hai cột; nếu không '
             'thì = Khối lượng × Đơn giá. Dòng không có giá luôn = 0.')
    note = fields.Text(string='Ghi chú')

    # ------------------------------------------------------------------
    # Compute
    # ------------------------------------------------------------------
    @api.depends('structure_id', 'package_id')
    def _compute_anchor(self):
        for line in self:
            st, pk = line.structure_id, line.package_id
            proj = st.project_id or pk.project_id
            line.project_id = proj
            line.subzone_id = st.subzone_id
            line.currency_id = (st.currency_id or pk.currency_id
                                or proj.currency_id)
            line.company_id = st.company_id or pk.company_id

    @api.depends('quantity', 'unit_price', 'amount_supply',
                 'amount_install', 'line_status', 'is_selected')
    def _compute_amount(self):
        for line in self:
            if line.line_status != 'priced' or not line.is_selected:
                line.amount = 0.0
                continue
            hai_cot = (line.amount_supply or 0.0) + (line.amount_install or 0.0)
            line.amount = hai_cot or (
                (line.quantity or 0.0) * (line.unit_price or 0.0))

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------
    @api.constrains('structure_id', 'package_id')
    def _check_anchor(self):
        for line in self:
            if not line.structure_id and not line.package_id:
                raise ValidationError(
                    'Dòng BOQ phải gắn vào một hạng mục hoặc một gói '
                    'thầu: "%s".' % (line.description or ''))

    @api.constrains('category_id', 'structure_id', 'package_id')
    def _check_category_same_project(self):
        for line in self:
            if line.category_id.project_id != line.project_id:
                raise ValidationError(
                    f'Nhóm chi phí "{line.category_id.display_name}" thuộc '
                    f'dự án khác. Nhóm chi phí phải cùng dự án với dòng '
                    f'BOQ "{line.description}".')

    @api.constrains('quantity', 'unit_price')
    def _check_non_negative(self):
        for line in self:
            if line.quantity < 0 or line.unit_price < 0:
                raise ValidationError(
                    f'Khối lượng và đơn giá không được âm '
                    f'(dòng "{line.description}").')
