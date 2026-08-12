# -*- coding: utf-8 -*-
"""Định mức xây dựng — §4.5 của vn_cost_data_pattern.md.

Bốn sự thật quyết định model, mỗi cái có bằng chứng:

1. **`norm.code` MỘT MÌNH KHÔNG PHẢI KHOÁ.** `AB.11311` của TT 12/2021 và
   của TT 38/2026 có thể là HAI công tác khác nhau (TT 38 thay TT 12 từ
   01/7/2026). Khoá thật = (`set_id`, `code`).

2. **Định mức là MA TRẬN, không phải list phẳng.** Chữ số cuối mã hiệu =
   SỐ CỘT. `AB.11300` (nhóm) → `AB.1131` (hàng: rộng≤3, sâu≤1) → `AB.11311`
   (× cột 1 = cấp đất I). Kiểm ngược trên bộ Harmonia Bay khớp hết.

3. **`uom` + bậc thợ + "thành phần công việc" treo ở cấp NHÓM**, item kế
   thừa. Nên có field gốc + field "effective" đi ngược cây tìm giá trị.

4. **`quantity` KHÔNG phải lúc nào cũng là số.** Định mức vận chuyển là HÀM
   BẬC THANG theo cự ly ⇒ `norm_type` = fixed | formula.

`norm.line.resource_id` trỏ tới `rp.resource` — đây là chỗ định mức (Core,
quốc gia) gặp tài nguyên (có giá ở Dự án). Đơn giá = Core × Dự án.
"""
from odoo import _, api, fields, models


class RpNormSet(models.Model):
    _name = 'rp.norm.set'
    _description = 'Bộ định mức (theo văn bản ban hành)'
    _order = 'issue_date desc, code'

    code = fields.Char(string='Ký hiệu', required=True, index=True,
                       help='VD: TT 38/2026, TT 12/2021')
    name = fields.Char(string='Tên', required=True, translate=True)
    doc_no = fields.Char(string='Số văn bản')
    issue_date = fields.Date(string='Ngày ban hành')
    effective_date = fields.Date(string='Ngày hiệu lực')
    publisher = fields.Selection([
        ('bxd', 'Bộ Xây dựng'),
        ('nganh', 'Bộ quản lý chuyên ngành'),
        ('tinh', 'UBND cấp tỉnh'),
    ], string='Cấp ban hành', default='bxd',
        help='NĐ 206/2026 Điều 34.1 + 35.2: Bộ chuyên ngành và UBND tỉnh '
             'cũng được ban hành định mức cho công tác BXD chưa có.')
    scope = fields.Char(string='Phạm vi',
                        help='VD: toàn quốc, hoặc tên tỉnh nếu do UBND ban hành')
    superseded_by_id = fields.Many2one(
        'rp.norm.set', string='Bị thay bởi',
        help='VD: TT 12/2021 → bị TT 38/2026 thay từ 01/7/2026. NĐ 206 Điều '
             '36.7: bộ cũ vẫn dùng được ĐẾN KHI có bản mới có hiệu lực.')
    is_superseded = fields.Boolean(
        compute='_compute_is_superseded', store=True)
    norm_ids = fields.One2many('rp.norm', 'set_id', string='Định mức')
    norm_count = fields.Integer(compute='_compute_norm_count')
    active = fields.Boolean(default=True)

    _uniq_code = models.Constraint(
        'unique(code)', 'Ký hiệu bộ định mức đã tồn tại.')

    @api.depends('superseded_by_id')
    def _compute_is_superseded(self):
        for r in self:
            r.is_superseded = bool(r.superseded_by_id)

    def _compute_norm_count(self):
        for r in self:
            r.norm_count = len(r.norm_ids)


class RpNorm(models.Model):
    _name = 'rp.norm'
    _description = 'Định mức (mã hiệu)'
    _parent_store = True
    _order = 'set_id, code'

    set_id = fields.Many2one(
        'rp.norm.set', string='Bộ định mức', required=True,
        ondelete='cascade', index=True)
    code = fields.Char(string='Mã hiệu', required=True, index=True,
                       help='VD: AB.11300 (nhóm), AB.11311 (item)')
    name = fields.Char(string='Tên công tác', required=True, translate=True)
    parent_id = fields.Many2one(
        'rp.norm', string='Cấp cha', ondelete='cascade', index=True,
        domain="[('set_id','=',set_id)]")
    parent_path = fields.Char(index=True, unaccent=False)
    child_ids = fields.One2many('rp.norm', 'parent_id', string='Cấp con')
    is_leaf = fields.Boolean(
        string='Là dòng định mức', compute='_compute_is_leaf', store=True,
        help='Node lá = item có hao phí. Node cha = nhóm/chương.')

    # ── treo ở cấp NHÓM, item kế thừa (fact 3) ──
    uom_id = fields.Many2one('uom.uom', string='Đơn vị')
    labor_grade = fields.Char(string='Bậc thợ', help='VD: 3,0/7')
    work_scope = fields.Text(string='Thành phần công việc')
    eff_uom_id = fields.Many2one(
        'uom.uom', string='Đơn vị (hiệu lực)',
        compute='_compute_effective', recursive=True,
        help='Đi ngược cây tìm đơn vị khai ở cấp nhóm.')
    eff_labor_grade = fields.Char(
        compute='_compute_effective', recursive=True)

    # ── ma trận (fact 2) ──
    row_label = fields.Char(string='Hàng (kích thước)',
                            help='VD: Rộng ≤3, Sâu ≤1')
    col_label = fields.Char(string='Cột (cấp đất/đá/loại)',
                            help='VD: Cấp đất I')

    # ── hao phí (fact 4) ──
    norm_type = fields.Selection([
        ('fixed', 'Số cố định'),
        ('formula', 'Công thức (vd vận chuyển theo cự ly)'),
    ], string='Kiểu', default='fixed')
    formula_note = fields.Char(
        string='Công thức',
        help='VD: Đm = Đm1 + Đm2×(L−1) với L≤5km')
    line_ids = fields.One2many('rp.norm.line', 'norm_id', string='Hao phí')

    active = fields.Boolean(default=True)

    _uniq_set_code = models.Constraint(
        'unique(set_id, code)',
        'Mã hiệu đã tồn tại trong bộ định mức này. '
        '(Cùng mã ở BỘ KHÁC thì được — đó là lý do khoá gồm cả bộ.)')

    @api.depends('child_ids')
    def _compute_is_leaf(self):
        for r in self:
            r.is_leaf = not r.child_ids

    @api.depends('uom_id', 'labor_grade', 'parent_id.eff_uom_id',
                 'parent_id.eff_labor_grade')
    def _compute_effective(self):
        for r in self:
            r.eff_uom_id = r.uom_id or r.parent_id.eff_uom_id
            r.eff_labor_grade = r.labor_grade or r.parent_id.eff_labor_grade

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for r in self:
            r.display_name = '%s %s' % (r.code or '', r.name or '')


class RpNormLine(models.Model):
    _name = 'rp.norm.line'
    _description = 'Hao phí định mức'
    _order = 'norm_id, resource_id'

    norm_id = fields.Many2one(
        'rp.norm', string='Định mức', required=True, ondelete='cascade')
    resource_id = fields.Many2one(
        'rp.resource', string='Tài nguyên', required=True,
        help='Trỏ tới rp.resource — chỗ định mức (Core) gặp tài nguyên '
             '(có giá ở Dự án).')
    resource_type = fields.Selection(
        related='resource_id.resource_type', store=True, string='Loại')
    quantity = fields.Float(string='Hao phí', digits=(16, 6),
                            help='Trên 1 đơn vị công tác. VD: 0,56 công/1m³')
    is_percent = fields.Boolean(
        string='Tính %', help='VD: "Máy khác 5%" — hao phí theo % tổng máy')
    note = fields.Char(string='Ghi chú')


class RpBuildup(models.Model):
    _name = 'rp.buildup'
    _description = 'Cấp phối (vữa / bê tông)'
    _order = 'code'

    code = fields.Char(string='Mã', required=True, index=True)
    name = fields.Char(string='Tên', required=True, translate=True)
    grade = fields.Char(string='Mác / cấp độ bền',
                        help='VD: M100 · B7,5 (bảng tương quan PL7 Ch.I TT38)')
    uom_id = fields.Many2one('uom.uom', string='Đơn vị')
    component_ids = fields.One2many(
        'rp.buildup.line', 'buildup_id', string='Thành phần cấp phối')
    active = fields.Boolean(default=True)

    _uniq_code = models.Constraint('unique(code)', 'Mã cấp phối đã tồn tại.')

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for r in self:
            r.display_name = '[%s] %s' % (r.code, r.name) if r.code else r.name


class RpBuildupLine(models.Model):
    _name = 'rp.buildup.line'
    _description = 'Thành phần cấp phối'
    _order = 'buildup_id, resource_id'

    buildup_id = fields.Many2one(
        'rp.buildup', string='Cấp phối', required=True, ondelete='cascade')
    resource_id = fields.Many2one(
        'rp.resource', string='Vật liệu', required=True)
    quantity = fields.Float(string='Định lượng', digits=(16, 6),
                            help='VD: xi măng kg/m³, cát m³/m³, nước lít/m³')
    note = fields.Char(string='Ghi chú')
