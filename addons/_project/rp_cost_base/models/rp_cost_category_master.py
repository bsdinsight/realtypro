# -*- coding: utf-8 -*-
"""rp.cost.category.master — Danh mục chi phí CHUẨN cấp công ty.

Mô hình hybrid theo thông lệ ngành (Procore/Primavera/SAP PS):
- Master là mỏ neo chuẩn cấp công ty, KHÔNG gắn dự án.
- Khi tạo dự án, cây master được COPY (instantiate) thành
  ``rp.cost.category`` của dự án — dự án tự do thêm mã đặc thù mà
  không ảnh hưởng dự án khác (category drift được kiểm soát bằng cờ
  ``is_project_specific``).
- Mỗi category dự án giữ ``master_category_id`` trỏ về master →
  benchmark chi phí CHÉO DỰ ÁN group theo mã master (điều kiện bắt
  buộc của so sánh chi phí/m² — RICS Cost analysis & benchmarking).

Quy tắc vàng: sửa master CHỈ ảnh hưởng dự án tạo MỚI. Không bao giờ
đồng bộ ngược vào danh mục dự án đang chạy (bài học Unifier/ACC:
structure đóng băng tại thời điểm instantiate).
"""
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class RpCostCategoryMaster(models.Model):
    _name = 'rp.cost.category.master'
    _description = 'Danh mục chi phí chuẩn (Master)'
    _order = 'sequence, code, name'
    _parent_store = True
    _parent_name = 'parent_id'

    name = fields.Char(string='Name', required=True, translate=True)
    code = fields.Char(string='Code')
    sequence = fields.Integer(default=10)

    parent_id = fields.Many2one(
        'rp.cost.category.master', string='Parent Category',
        index=True, ondelete='restrict')
    child_ids = fields.One2many(
        'rp.cost.category.master', 'parent_id', string='Sub-categories')
    parent_path = fields.Char(index=True)
    level = fields.Integer(
        compute='_compute_level', store=True, recursive=True,
        help='Depth from root (1, 2, or 3). Enforced max 3.')
    complete_path = fields.Char(
        compute='_compute_complete_path', store=True, recursive=True)

    is_contingency = fields.Boolean(string='Contingency')
    is_land_cost = fields.Boolean(string='Land Cost')
    description = fields.Text()
    active = fields.Boolean(default=True)

    project_category_count = fields.Integer(
        compute='_compute_project_category_count',
        string='Dự án dùng',
        help='Số category dự án đang trỏ về mã master này.')

    @api.depends('parent_id', 'parent_id.level')
    def _compute_level(self):
        for rec in self:
            rec.level = (rec.parent_id.level or 0) + 1 \
                if rec.parent_id else 1

    @api.depends('name', 'parent_id', 'parent_id.complete_path')
    def _compute_complete_path(self):
        for rec in self:
            if rec.parent_id and rec.parent_id.complete_path:
                rec.complete_path = '%s / %s' % (
                    rec.parent_id.complete_path, rec.name or '')
            else:
                rec.complete_path = rec.name or ''

    def _compute_project_category_count(self):
        Cat = self.env['rp.cost.category']
        for rec in self:
            rec.project_category_count = Cat.search_count(
                [('master_category_id', '=', rec.id)])

    @api.constrains('parent_id')
    def _check_max_3_levels(self):
        for rec in self:
            if rec.level and rec.level > 3:
                raise ValidationError(
                    'Cost category tree is limited to 3 levels.')

    def init(self):
        # init() được Odoo gọi ở check_tables_exist cho MỌI lần update bất kỳ
        # module nào — trên DB chưa từng -u rp_cost_base bảng còn chưa tạo,
        # SQL thẳng sẽ crash registry. Guard cho tới khi bảng tồn tại.
        self.env.cr.execute(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_name = 'rp_cost_category_master'")
        if not self.env.cr.fetchone():
            return
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
                rp_cost_category_master_unique_code
            ON rp_cost_category_master (code)
            WHERE code IS NOT NULL
        """)

    # ------------------------------------------------------------------
    # Seed + instantiate
    # ------------------------------------------------------------------
    @api.model
    def _ensure_seeded(self):
        """Seed master từ bộ mặc định VN nếu master còn trống."""
        if self.search_count([]):
            return
        from .rp_cost_category import DEFAULT_COST_CATEGORIES
        code_to_record = {}
        for entry in DEFAULT_COST_CATEGORIES:
            rec = self.create({
                'name': entry['name'],
                'code': entry['code'],
                'sequence': entry.get('sequence', 10),
                'is_contingency': entry.get('is_contingency', False),
                'is_land_cost': entry.get('is_land_cost', False),
                'description': entry.get('description', ''),
            })
            code_to_record[entry['code']] = rec
        for entry in DEFAULT_COST_CATEGORIES:
            parent = code_to_record.get(entry['code'])
            for child in entry.get('children', []):
                self.create({
                    'parent_id': parent.id if parent else False,
                    'name': child['name'],
                    'code': child['code'],
                    'sequence': child.get('sequence', 10),
                    'is_contingency': child.get('is_contingency', False),
                    'is_land_cost': child.get('is_land_cost', False),
                    'description': child.get('description', ''),
                })

    def _copy_tree_to_project(self, project):
        """Instantiate toàn bộ cây master (active) vào dự án, giữ link
        master_category_id trên từng bản copy."""
        Cat = self.env['rp.cost.category']
        mapping = {}
        for m in self.search([], order='parent_path'):
            parent = mapping.get(m.parent_id.id) if m.parent_id else None
            mapping[m.id] = Cat.create({
                'project_id': project.id,
                'parent_id': parent.id if parent else False,
                'name': m.name,
                'code': m.code,
                'sequence': m.sequence,
                'is_contingency': m.is_contingency,
                'is_land_cost': m.is_land_cost,
                'description': m.description or '',
                'master_category_id': m.id,
            })
        return mapping
