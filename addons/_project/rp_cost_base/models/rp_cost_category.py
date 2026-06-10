# -*- coding: utf-8 -*-
"""rp.cost.category — Project-scoped cost classification tree.

Each project has its own tree, auto-seeded with a Vietnamese default
set when the project is created. Maximum 3 levels enforced. Users
can add more categories per-project after creation; new categories
are project-scoped (project A's edits don't leak to project B).

Cost category answers WHAT KIND of cost (Construction, Equipment, ...).
For WHERE the cost belongs (Hạng mục, Sub-hạng mục), see rp.structure.
"""

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class RpCostCategory(models.Model):
    _name = 'rp.cost.category'
    _description = 'Cost Category / Nhóm chi phí'
    _order = 'project_id, sequence, code, name'
    _parent_store = True
    _parent_name = 'parent_id'

    # ----- Identity
    name = fields.Char(string='Name', required=True, translate=True)
    code = fields.Char(string='Code')
    sequence = fields.Integer(default=10)

    # ----- Hierarchy
    project_id = fields.Many2one(
        're.project', string='Project',
        required=True, ondelete='cascade', index=True,
    )
    parent_id = fields.Many2one(
        'rp.cost.category', string='Parent Category',
        index=True, ondelete='restrict',
    )
    child_ids = fields.One2many(
        'rp.cost.category', 'parent_id',
        string='Sub-categories',
    )
    parent_path = fields.Char(index=True)
    level = fields.Integer(
        compute='_compute_level', store=True, recursive=True,
        help='Depth from root (1, 2, or 3). Enforced max 3.',
    )
    complete_path = fields.Char(
        compute='_compute_complete_path', store=True, recursive=True,
        help='Slash-separated path: "L1 / L2 / L3".',
    )

    # ----- Flags
    is_contingency = fields.Boolean(
        string='Contingency',
        help='Marks this category as contingency / dự phòng. '
             'Useful for finding all contingency lines in a cost plan.',
    )
    is_land_cost = fields.Boolean(
        string='Land Cost',
        help='Marks this category as land-related (CapEx categorization).',
    )

    # ----- Metadata
    description = fields.Text()
    active = fields.Boolean(default=True)

    # ----- Computeds
    @api.depends('parent_id', 'parent_id.level')
    def _compute_level(self):
        for rec in self:
            if not rec.parent_id:
                rec.level = 1
            else:
                rec.level = (rec.parent_id.level or 0) + 1

    @api.depends('name', 'parent_id', 'parent_id.complete_path')
    def _compute_complete_path(self):
        for rec in self:
            if rec.parent_id and rec.parent_id.complete_path:
                rec.complete_path = f'{rec.parent_id.complete_path} / {rec.name}'
            else:
                rec.complete_path = rec.name or ''

    # ----- Constraints
    @api.constrains('parent_id')
    def _check_no_cycle(self):
        if self._has_cycle():
            raise ValidationError(
                'Cost categories cannot form a circular hierarchy.'
            )

    @api.constrains('parent_id', 'project_id')
    def _check_parent_same_project(self):
        for rec in self:
            if rec.parent_id and rec.parent_id.project_id != rec.project_id:
                raise ValidationError(
                    'Parent cost category must belong to the same project.'
                )

    @api.constrains('parent_id')
    def _check_max_3_levels(self):
        for rec in self:
            if rec.level and rec.level > 3:
                raise ValidationError(
                    'Cost category tree is limited to 3 levels.'
                )

    @property
    def _table_query(self):
        return None

    # Postgres-level: code unique per project when code is set.
    # Implemented as a partial unique index.
    def init(self):
        # Create the partial unique index if missing
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS rp_cost_category_unique_code_per_project
            ON rp_cost_category (project_id, code)
            WHERE code IS NOT NULL
        """)

    # ----- Helper: seed Vietnamese default set
    @api.model
    def _seed_defaults_for_project(self, project):
        """Seed the Vietnamese default cost category tree on project.

        Idempotent: if the project already has any categories, this
        is a no-op (we do not duplicate; we do not "merge").

        Customers who want a different starting set can clear the
        tree first and re-create their own categories. The hook
        runs at project create time; on subsequent edits it does
        nothing.
        """
        existing = self.search_count([('project_id', '=', project.id)])
        if existing:
            return

        # Two-pass create: L1 first, then L2 with parent resolved.
        code_to_record = {}
        for entry in DEFAULT_COST_CATEGORIES:
            cat = self.create({
                'project_id': project.id,
                'name': entry['name'],
                'code': entry['code'],
                'sequence': entry.get('sequence', 10),
                'is_contingency': entry.get('is_contingency', False),
                'is_land_cost': entry.get('is_land_cost', False),
                'description': entry.get('description', ''),
            })
            code_to_record[entry['code']] = cat

        for entry in DEFAULT_COST_CATEGORIES:
            for child in entry.get('children', []):
                parent = code_to_record.get(entry['code'])
                if not parent:
                    continue
                self.create({
                    'project_id': project.id,
                    'parent_id': parent.id,
                    'name': child['name'],
                    'code': child['code'],
                    'sequence': child.get('sequence', 10),
                    'is_contingency': child.get('is_contingency', False),
                    'is_land_cost': child.get('is_land_cost', False),
                    'description': child.get('description', ''),
                })


# =============================================================================
# Vietnamese real-estate default cost category tree
# 11 L1 + 56 L2 = 67 records seeded per project.
#
# Source: Vinhomes Cần Giờ template document (Section 5).
# =============================================================================
DEFAULT_COST_CATEGORIES = [
    {
        'code': '1', 'sequence': 10,
        'name': 'Chi phí đất, pháp lý, GPMB',
        'is_land_cost': True,
        'children': [
            {'code': '1.1', 'sequence': 10, 'name': 'Chi phí đất / tiền sử dụng đất / tiền thuê đất', 'is_land_cost': True},
            {'code': '1.2', 'sequence': 20, 'name': 'Chi phí bồi thường, giải phóng mặt bằng', 'is_land_cost': True},
            {'code': '1.3', 'sequence': 30, 'name': 'Chi phí chuyển mục đích sử dụng đất', 'is_land_cost': True},
            {'code': '1.4', 'sequence': 40, 'name': 'Thuế trước bạ / phí đất đai', 'is_land_cost': True},
            {'code': '1.5', 'sequence': 50, 'name': 'Chi phí pháp lý dự án'},
            {'code': '1.6', 'sequence': 60, 'name': 'Chi phí quy hoạch / phê duyệt chủ trương'},
        ],
    },
    {
        'code': '2', 'sequence': 20,
        'name': 'Chi phí chuẩn bị đầu tư',
        'children': [
            {'code': '2.1', 'sequence': 10, 'name': 'Khảo sát địa hình'},
            {'code': '2.2', 'sequence': 20, 'name': 'Khảo sát địa chất'},
            {'code': '2.3', 'sequence': 30, 'name': 'Khảo sát thủy văn / môi trường biển'},
            {'code': '2.4', 'sequence': 40, 'name': 'Lập báo cáo tiền khả thi / khả thi'},
            {'code': '2.5', 'sequence': 50, 'name': 'Đánh giá tác động môi trường'},
            {'code': '2.6', 'sequence': 60, 'name': 'Thẩm định / phê duyệt dự án'},
            {'code': '2.7', 'sequence': 70, 'name': 'Chi phí chuẩn bị khác'},
        ],
    },
    {
        'code': '3', 'sequence': 30,
        'name': 'Chi phí xây dựng công trình',
        'children': [
            {'code': '3.1', 'sequence': 10, 'name': 'San nền / xử lý nền'},
            {'code': '3.2', 'sequence': 20, 'name': 'Móng / cọc / tầng hầm'},
            {'code': '3.3', 'sequence': 30, 'name': 'Kết cấu thân'},
            {'code': '3.4', 'sequence': 40, 'name': 'Kiến trúc / hoàn thiện'},
            {'code': '3.5', 'sequence': 50, 'name': 'MEP'},
            {'code': '3.6', 'sequence': 60, 'name': 'PCCC'},
            {'code': '3.7', 'sequence': 70, 'name': 'Facade / mặt dựng'},
            {'code': '3.8', 'sequence': 80, 'name': 'Nội thất xây dựng cơ bản'},
            {'code': '3.9', 'sequence': 90, 'name': 'Xây dựng khác'},
        ],
    },
    {
        'code': '4', 'sequence': 40,
        'name': 'Chi phí thiết bị',
        'children': [
            {'code': '4.1', 'sequence': 10, 'name': 'Thang máy / thang cuốn'},
            {'code': '4.2', 'sequence': 20, 'name': 'Thiết bị MEP chính'},
            {'code': '4.3', 'sequence': 30, 'name': 'Thiết bị PCCC'},
            {'code': '4.4', 'sequence': 40, 'name': 'Thiết bị khách sạn / FF&E'},
            {'code': '4.5', 'sequence': 50, 'name': 'Thiết bị y tế'},
            {'code': '4.6', 'sequence': 60, 'name': 'Thiết bị bến du thuyền / cảng'},
            {'code': '4.7', 'sequence': 70, 'name': 'Thiết bị công viên / vui chơi giải trí'},
            {'code': '4.8', 'sequence': 80, 'name': 'Thiết bị khác'},
        ],
    },
    {
        'code': '5', 'sequence': 50,
        'name': 'Chi phí hạ tầng kỹ thuật',
        'children': [
            {'code': '5.1', 'sequence': 10, 'name': 'Đường giao thông nội khu'},
            {'code': '5.2', 'sequence': 20, 'name': 'Cầu / kè / bến / cảng'},
            {'code': '5.3', 'sequence': 30, 'name': 'Cấp nước'},
            {'code': '5.4', 'sequence': 40, 'name': 'Thoát nước mưa'},
            {'code': '5.5', 'sequence': 50, 'name': 'Thoát nước thải'},
            {'code': '5.6', 'sequence': 60, 'name': 'Xử lý nước thải'},
            {'code': '5.7', 'sequence': 70, 'name': 'Cấp điện / trạm điện'},
            {'code': '5.8', 'sequence': 80, 'name': 'Viễn thông / ICT'},
            {'code': '5.9', 'sequence': 90, 'name': 'Chiếu sáng công cộng'},
            {'code': '5.10', 'sequence': 100, 'name': 'Hạ tầng kỹ thuật khác'},
        ],
    },
    {
        'code': '6', 'sequence': 60,
        'name': 'Chi phí cảnh quan, mặt nước, môi trường',
        'children': [
            {'code': '6.1', 'sequence': 10, 'name': 'Cây xanh / cảnh quan'},
            {'code': '6.2', 'sequence': 20, 'name': 'Công viên / quảng trường'},
            {'code': '6.3', 'sequence': 30, 'name': 'Hồ nước / lagoon / kênh nội khu'},
            {'code': '6.4', 'sequence': 40, 'name': 'Bãi biển nhân tạo / kè biển'},
            {'code': '6.5', 'sequence': 50, 'name': 'Sân golf'},
            {'code': '6.6', 'sequence': 60, 'name': 'Bảo tồn / phục hồi môi trường'},
            {'code': '6.7', 'sequence': 70, 'name': 'Cảnh quan khác'},
        ],
    },
    {
        'code': '7', 'sequence': 70,
        'name': 'Chi phí tư vấn',
        'children': [
            {'code': '7.1', 'sequence': 10, 'name': 'Quy hoạch tổng thể'},
            {'code': '7.2', 'sequence': 20, 'name': 'Thiết kế concept'},
            {'code': '7.3', 'sequence': 30, 'name': 'Thiết kế cơ sở'},
            {'code': '7.4', 'sequence': 40, 'name': 'Thiết kế kỹ thuật / bản vẽ thi công'},
            {'code': '7.5', 'sequence': 50, 'name': 'Thẩm tra thiết kế'},
            {'code': '7.6', 'sequence': 60, 'name': 'Thẩm tra dự toán'},
            {'code': '7.7', 'sequence': 70, 'name': 'Lập và đánh giá hồ sơ thầu'},
            {'code': '7.8', 'sequence': 80, 'name': 'Tư vấn giám sát'},
            {'code': '7.9', 'sequence': 90, 'name': 'Tư vấn khác'},
        ],
    },
    {
        'code': '8', 'sequence': 80,
        'name': 'Chi phí quản lý dự án',
        'children': [
            {'code': '8.1', 'sequence': 10, 'name': 'Ban quản lý dự án chủ đầu tư'},
            {'code': '8.2', 'sequence': 20, 'name': 'Tư vấn quản lý dự án thuê ngoài'},
            {'code': '8.3', 'sequence': 30, 'name': 'Chi phí văn phòng dự án'},
            {'code': '8.4', 'sequence': 40, 'name': 'Chi phí công cụ / phần mềm PMO'},
            {'code': '8.5', 'sequence': 50, 'name': 'Quản lý dự án khác'},
        ],
    },
    {
        'code': '9', 'sequence': 90,
        'name': 'Chi phí tài chính & thuế',
        'children': [
            {'code': '9.1', 'sequence': 10, 'name': 'Lãi vay capitalized trong xây dựng'},
            {'code': '9.2', 'sequence': 20, 'name': 'Phí thu xếp vốn / phí ngân hàng'},
            {'code': '9.3', 'sequence': 30, 'name': 'Phí kết nối hạ tầng / cấp phép'},
            {'code': '9.4', 'sequence': 40, 'name': 'Thuế phi xây dựng / phí khác'},
        ],
    },
    {
        'code': '10', 'sequence': 100,
        'name': 'Chi phí marketing và bán hàng (capex)',
        'children': [
            {'code': '10.1', 'sequence': 10, 'name': 'Showflat / sales gallery'},
            {'code': '10.2', 'sequence': 20, 'name': 'Event launch / mở bán'},
            {'code': '10.3', 'sequence': 30, 'name': 'Brand / PR capex'},
            {'code': '10.4', 'sequence': 40, 'name': 'Marketing capex khác'},
        ],
    },
    {
        'code': '11', 'sequence': 110,
        'name': 'Dự phòng',
        'is_contingency': True,
        'children': [
            {'code': '11.1', 'sequence': 10, 'name': 'Dự phòng khối lượng phát sinh', 'is_contingency': True},
            {'code': '11.2', 'sequence': 20, 'name': 'Dự phòng trượt giá', 'is_contingency': True},
            {'code': '11.3', 'sequence': 30, 'name': 'Dự phòng rủi ro khác', 'is_contingency': True},
        ],
    },
]
