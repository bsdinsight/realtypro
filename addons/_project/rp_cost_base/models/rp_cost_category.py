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
        help='Độ sâu từ gốc (1 hoặc 2). Tối đa 2 cấp.',
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

    is_finance_cost = fields.Boolean(
        string='Chi phí tài chính',
        help='Nhóm chi phí tài chính (lãi vay vốn hoá, phí thu '
             'xếp vốn, phí bảo lãnh...). Được LOẠI khỏi CTC và '
             'khỏi gốc tính vốn tự có — tránh vòng lặp lãi vay '
             '(tài liệu nghiệp vụ §3).',
    )
    is_land_cost = fields.Boolean(
        string='Land Cost',
        help='Marks this category as land-related (CapEx categorization).',
    )

    # ----- Liên kết Master (hybrid: master → copy per project → map-back)
    master_category_id = fields.Many2one(
        'rp.cost.category.master', string='Mã chuẩn (Master)',
        index=True, ondelete='set null',
        help='Mã master mà category này được copy từ đó (hoặc map về). '
             'Benchmark chi phí chéo dự án group theo mã này. Để trống '
             '= mã đặc thù riêng của dự án.')
    is_project_specific = fields.Boolean(
        string='Đặc thù dự án', compute='_compute_is_project_specific',
        store=True,
        help='Không map về danh mục chuẩn công ty — mã riêng của dự án '
             '(vd bệnh viện có nhóm chi phí không dự án nào khác có).')

    # ----- Metadata
    description = fields.Text()
    active = fields.Boolean(default=True)

    @api.depends('master_category_id')
    def _compute_is_project_specific(self):
        for rec in self:
            rec.is_project_specific = not rec.master_category_id

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
            if rec.level and rec.level > 2:
                raise ValidationError(
                    'Cây nhóm chi phí chỉ có TỐI ĐA 2 CẤP (anh Đại chốt '
                    '2026-08-10). Cấp 3 làm vỡ roll-up dự toán và không '
                    'ai dùng — chi tiết hơn thì dùng trường "Yếu tố chi '
                    'phí" trên dòng BOQ.'
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

    # ----- Helper: instantiate từ Master catalog (hybrid model)
    @api.model
    def _seed_defaults_for_project(self, project):
        """Copy cây danh mục chuẩn (Master) vào dự án mới.

        Idempotent: dự án đã có category thì no-op. Master trống thì
        tự seed bộ mặc định VN vào master trước (lần chạy đầu tiên).
        Mỗi category dự án giữ ``master_category_id`` để benchmark
        chéo dự án; dự án thêm mã riêng sau đó sẽ mang cờ
        ``is_project_specific``.
        """
        existing = self.search_count([('project_id', '=', project.id)])
        if existing:
            return
        Master = self.env['rp.cost.category.master']
        Master._ensure_seeded()
        Master._copy_tree_to_project(project)


# =============================================================================
# Vietnamese real-estate default cost category tree
# 11 L1 + 56 L2 = 67 records seeded per project.
#
# Nguồn: mẫu điển hình cơ cấu chi phí dự án BĐS Việt Nam.
# =============================================================================
# ── BỘ DANH MỤC CHI PHÍ CHUẨN — 10 NHÓM CẤP 1 ──────────────────────
# Anh Đại chốt 2026-08-10: rút gọn còn ĐÚNG 10 nhóm cấp 1 cho dễ nhớ,
# chia theo HẠNG MỤC CÔNG VIỆC (WBS) — tách phần xây lắp thành Kết cấu /
# Hoàn thiện / MEP vì đó là cách chia gói thầu và cách NH theo dõi giải
# ngân. Yếu tố chi phí (vật liệu / nhân công / máy / thầu phụ / chung)
# KHÔNG nằm trong cây này mà là một TRƯỜNG riêng trên dòng BOQ — tránh
# nhân chéo 10 × 5 nhóm.
# Thuế và Marketing gộp vào nhóm 08 (chi phí khác) để giữ đúng con số 10.
# Nhóm 09 (tài chính) và 10 (dự phòng) mặc định BỊ LOẠI khỏi CTC khi tính
# Nhu cầu vốn — theo tài liệu nghiệp vụ §3 (chỉ tính chi phí thực phát sinh
# dòng tiền, có hồ sơ hợp lệ) và để tránh vòng lặp lãi vay.
DEFAULT_COST_CATEGORIES = [
    {
        'code': '01', 'sequence': 10, 'is_land_cost': True,
        'name': 'Chi phí đất & mặt bằng',
        'description': 'Đất, GPMB, đền bù, chuẩn bị mặt bằng.',
        'children': [
            {'code': '01.1', 'sequence': 10, 'is_land_cost': True, 'name': 'Tiền sử dụng đất / tiền thuê đất'},
            {'code': '01.2', 'sequence': 20, 'is_land_cost': True, 'name': 'Bồi thường, hỗ trợ, tái định cư'},
            {'code': '01.3', 'sequence': 30, 'is_land_cost': True, 'name': 'Chuyển mục đích sử dụng đất, thuế phí đất'},
            {'code': '01.4', 'sequence': 40, 'name': 'Di dời hạ tầng, mồ mả, vật kiến trúc'},
            {'code': '01.5', 'sequence': 50, 'name': 'Rà phá bom mìn, dò tìm vật cản'},
            {'code': '01.6', 'sequence': 60, 'name': 'San lấp, chuẩn bị mặt bằng'},
            {'code': '01.7', 'sequence': 70, 'name': 'Pháp lý dự án, quy hoạch, chủ trương'},
        ],
    },
    {
        'code': '02', 'sequence': 20,
        'name': 'Chi phí thiết kế & tư vấn',
        'description': 'Thiết kế, khảo sát, tư vấn, PM/CM.',
        'children': [
            {'code': '02.1', 'sequence': 10, 'name': 'Khảo sát địa hình, địa chất, thuỷ văn'},
            {'code': '02.2', 'sequence': 20, 'name': 'Lập báo cáo tiền khả thi / khả thi'},
            {'code': '02.3', 'sequence': 30, 'name': 'Thiết kế (concept, cơ sở, kỹ thuật, BVTC)'},
            {'code': '02.4', 'sequence': 40, 'name': 'Thẩm tra, thẩm định thiết kế & dự toán'},
            {'code': '02.5', 'sequence': 50, 'name': 'Tư vấn quản lý dự án (PM/CM)'},
            {'code': '02.6', 'sequence': 60, 'name': 'Tư vấn giám sát (TVGS)'},
            {'code': '02.7', 'sequence': 70, 'name': 'Đánh giá tác động môi trường, PCCC, chuyên ngành'},
            {'code': '02.8', 'sequence': 80, 'name': 'Tư vấn khác'},
        ],
    },
    {
        'code': '03', 'sequence': 30,
        'name': 'Chi phí kết cấu & phần thô',
        'description': 'Móng, kết cấu, xây dựng phần thô.',
        'children': [
            {'code': '03.1', 'sequence': 10, 'name': 'Cọc, tường vây, xử lý nền'},
            {'code': '03.2', 'sequence': 20, 'name': 'Đào đất, chống vách, hạ mực nước ngầm'},
            {'code': '03.3', 'sequence': 30, 'name': 'Móng, đài, giằng'},
            {'code': '03.4', 'sequence': 40, 'name': 'Kết cấu bê tông cốt thép thân'},
            {'code': '03.5', 'sequence': 50, 'name': 'Kết cấu thép'},
            {'code': '03.6', 'sequence': 60, 'name': 'Xây thô, tường bao che'},
            {'code': '03.7', 'sequence': 70, 'name': 'Chống thấm phần ngầm'},
            {'code': '03.8', 'sequence': 80, 'name': 'Kết cấu & phần thô khác'},
        ],
    },
    {
        'code': '04', 'sequence': 40,
        'name': 'Chi phí kiến trúc & hoàn thiện',
        'description': 'Kiến trúc, façade, hoàn thiện.',
        'children': [
            {'code': '04.1', 'sequence': 10, 'name': 'Hoàn thiện sàn, tường, trần'},
            {'code': '04.2', 'sequence': 20, 'name': 'Cửa, vách kính, lan can'},
            {'code': '04.3', 'sequence': 30, 'name': 'Mặt dựng / façade'},
            {'code': '04.4', 'sequence': 40, 'name': 'Sơn, chống thấm hoàn thiện'},
            {'code': '04.5', 'sequence': 50, 'name': 'Thiết bị vệ sinh, phụ kiện'},
            {'code': '04.6', 'sequence': 60, 'name': 'Nội thất cố định (fit-out)'},
            {'code': '04.7', 'sequence': 70, 'name': 'Hoàn thiện khác'},
        ],
    },
    {
        'code': '05', 'sequence': 50,
        'name': 'Chi phí cơ điện (MEP)',
        'description': 'Điện, nước, HVAC, PCCC, ELV...',
        'children': [
            {'code': '05.1', 'sequence': 10, 'name': 'Điện động lực & chiếu sáng'},
            {'code': '05.2', 'sequence': 20, 'name': 'Cấp thoát nước trong nhà'},
            {'code': '05.3', 'sequence': 30, 'name': 'Điều hoà, thông gió (HVAC)'},
            {'code': '05.4', 'sequence': 40, 'name': 'Phòng cháy chữa cháy (PCCC)'},
            {'code': '05.5', 'sequence': 50, 'name': 'Điện nhẹ (ELV, BMS, camera, mạng)'},
            {'code': '05.6', 'sequence': 60, 'name': 'Thang máy, thang cuốn'},
            {'code': '05.7', 'sequence': 70, 'name': 'Trạm biến áp, máy phát điện'},
            {'code': '05.8', 'sequence': 80, 'name': 'Cơ điện khác'},
        ],
    },
    {
        'code': '06', 'sequence': 60,
        'name': 'Chi phí hạ tầng & ngoài nhà',
        'description': 'Đường, cảnh quan, hạ tầng kỹ thuật ngoài nhà.',
        'children': [
            {'code': '06.1', 'sequence': 10, 'name': 'Đường giao thông nội bộ, sân bãi'},
            {'code': '06.2', 'sequence': 20, 'name': 'Cấp thoát nước ngoài nhà'},
            {'code': '06.3', 'sequence': 30, 'name': 'Cấp điện, chiếu sáng ngoài nhà'},
            {'code': '06.4', 'sequence': 40, 'name': 'Hạ tầng viễn thông ngoài nhà'},
            {'code': '06.5', 'sequence': 50, 'name': 'Cảnh quan, cây xanh, mặt nước'},
            {'code': '06.6', 'sequence': 60, 'name': 'Tường rào, cổng, nhà bảo vệ'},
            {'code': '06.7', 'sequence': 70, 'name': 'Xử lý nước thải, môi trường'},
            {'code': '06.8', 'sequence': 80, 'name': 'Hạ tầng & ngoài nhà khác'},
        ],
    },
    {
        'code': '07', 'sequence': 70,
        'name': 'Chi phí thiết bị & công nghệ',
        'description': 'Máy móc, thiết bị, hệ thống công nghệ.',
        'children': [
            {'code': '07.1', 'sequence': 10, 'name': 'Thiết bị công nghệ / dây chuyền'},
            {'code': '07.2', 'sequence': 20, 'name': 'Thiết bị chuyên dụng (y tế, thí nghiệm...)'},
            {'code': '07.3', 'sequence': 30, 'name': 'Thiết bị văn phòng, nội thất rời'},
            {'code': '07.4', 'sequence': 40, 'name': 'Vận chuyển, lắp đặt, chạy thử'},
            {'code': '07.5', 'sequence': 50, 'name': 'Đào tạo, chuyển giao công nghệ'},
            {'code': '07.6', 'sequence': 60, 'name': 'Thiết bị khác'},
        ],
    },
    {
        'code': '08', 'sequence': 80,
        'name': 'Chi phí quản lý & chi phí khác',
        'description': 'Quản lý dự án, công trường, pháp lý, kiểm định, '
                       'bảo hiểm, thuế, marketing và chi phí khác.',
        'children': [
            {'code': '08.1', 'sequence': 10, 'name': 'Chi phí quản lý dự án / Ban điều hành'},
            {'code': '08.2', 'sequence': 20, 'name': 'Chi phí công trường (lán trại, an toàn, vệ sinh MT)'},
            {'code': '08.3', 'sequence': 30, 'name': 'Bảo hiểm công trình, bảo hiểm trách nhiệm'},
            {'code': '08.4', 'sequence': 40, 'name': 'Kiểm định, thí nghiệm, nghiệm thu nhà nước'},
            {'code': '08.5', 'sequence': 50, 'name': 'Lệ phí, thẩm định, thủ tục hành chính'},
            {'code': '08.6', 'sequence': 60, 'name': 'Thuế, phí (VAT không khấu trừ, thuế nhà thầu)'},
            {'code': '08.7', 'sequence': 70, 'name': 'Marketing & bán hàng (capex)'},
            {'code': '08.8', 'sequence': 80, 'name': 'Chi phí khác'},
        ],
    },
    {
        'code': '09', 'sequence': 90, 'is_finance_cost': True,
        'name': 'Chi phí tài chính',
        'description': 'Lãi vay, phí tín dụng và chi phí tài chính được '
                       'phân bổ cho dự án. Mặc định LOẠI khỏi CTC khi '
                       'tính Nhu cầu vốn (tránh vòng lặp lãi vay).',
        'children': [
            {'code': '09.1', 'sequence': 10, 'is_finance_cost': True, 'name': 'Lãi vay trong thời gian xây dựng (vốn hoá)'},
            {'code': '09.2', 'sequence': 20, 'is_finance_cost': True, 'name': 'Phí thu xếp vốn, phí cam kết'},
            {'code': '09.3', 'sequence': 30, 'is_finance_cost': True, 'name': 'Phí bảo lãnh ngân hàng'},
            {'code': '09.4', 'sequence': 40, 'is_finance_cost': True, 'name': 'Chênh lệch tỷ giá, chi phí tài chính khác'},
        ],
    },
    {
        'code': '10', 'sequence': 100, 'is_contingency': True,
        'name': 'Dự phòng',
        'description': 'Dự phòng khối lượng, trượt giá, rủi ro. Mặc định '
                       'LOẠI khỏi CTC (chưa phát sinh, chưa có hồ sơ).',
        'children': [
            {'code': '10.1', 'sequence': 10, 'is_contingency': True, 'name': 'Dự phòng khối lượng phát sinh'},
            {'code': '10.2', 'sequence': 20, 'is_contingency': True, 'name': 'Dự phòng trượt giá'},
            {'code': '10.3', 'sequence': 30, 'is_contingency': True, 'name': 'Dự phòng rủi ro khác'},
        ],
    },
]
