# -*- coding: utf-8 -*-
"""Tài nguyên đơn giá — §4.3 của vn_cost_data_pattern.md.

Ba quyết định lõi, mỗi cái có bằng chứng:

1. `resource_type` là FIELD, KHÔNG phải cấp cây. Xác nhận 4 nguồn độc lập
   (Procore/Sage/HeavyBid/DDC). "Đổ bê tông" tiêu cả nhân công lẫn vật liệu
   → nếu type là cấp thì phải nhân bản item. HeavyBid nhét type vào ký tự
   đầu mã → bị gọi là anti-pattern thập niên 1980. VN cũng làm y hệt
   (NC2357, M101.0101) ⇒ ĐỌC mã để parse, đừng LẤY mã làm model.

2. Ba khoá, một định danh: `code` (của mình, tiếng Việt) là định danh;
   `gxd_code` (V10280) và `unspsc_code` (30111601) chỉ để MAP. Vật liệu VN
   không có mã chuẩn quốc gia — nhà nước gọi bằng tên (xác nhận PL7 TT38).

3. Cây danh mục 2 cấp là QUY ƯỚC, schema để vô hạn (Procore 6/2025 phải nới
   group lên 5 cấp — đừng khoá cứng). Cây định mức (norm) thì 3 cấp — model
   KHÁC, quy ước KHÁC.
"""
from odoo import _, api, fields, models


class RpResourceCategory(models.Model):
    _name = 'rp.resource.category'
    _description = 'Nhóm tài nguyên đơn giá'
    _parent_store = True
    _order = 'complete_name'

    name = fields.Char(string='Tên', required=True, translate=True)
    code = fields.Char(string='Mã', index=True,
                       help='VD: M101 (nhóm máy), M101.0100 (loại máy)')
    parent_id = fields.Many2one(
        'rp.resource.category', string='Nhóm cha', ondelete='cascade',
        index=True)
    parent_path = fields.Char(index=True, unaccent=False)
    child_ids = fields.One2many(
        'rp.resource.category', 'parent_id', string='Nhóm con')
    complete_name = fields.Char(
        string='Đường dẫn', compute='_compute_complete_name',
        recursive=True, store=True)
    resource_count = fields.Integer(
        string='Số tài nguyên', compute='_compute_resource_count')
    active = fields.Boolean(default=True)

    @api.depends('name', 'parent_id.complete_name')
    def _compute_complete_name(self):
        for c in self:
            c.complete_name = (
                '%s / %s' % (c.parent_id.complete_name, c.name)
                if c.parent_id else c.name)

    def _compute_resource_count(self):
        for c in self:
            c.resource_count = self.env['rp.resource'].search_count(
                [('categ_id', 'child_of', c.id)])


class RpResource(models.Model):
    _name = 'rp.resource'
    _description = 'Tài nguyên đơn giá (vật tư / nhân công / máy)'
    _order = 'resource_type, code'

    # ── Ba khoá, một định danh ──────────────────────────────────────
    code = fields.Char(string='Mã', required=True, index=True,
                       help='Mã của mình — định danh, tiếng Việt. '
                            'VD: NC2357, M101.0101, VL.CAT.001')
    gxd_code = fields.Char(
        string='Mã GXD', index=True,
        help='Mã trong phần mềm Dự toán GXD (VD: V10280). Chỉ để MAP khi '
             'đọc file khách — KHÔNG phải mã nhà nước.')
    unspsc_code = fields.Char(
        string='Mã UNSPSC',
        help='Mã phân loại quốc tế (VD: 30111601 = Cement). "Hộ chiếu" để '
             'liên thông — UNSPSC dừng ở LOẠI, không xuống tới PCB30/PCB40.')

    name = fields.Char(string='Tên', required=True, translate=True)
    uom_id = fields.Many2one('uom.uom', string='Đơn vị', required=True)

    # ── resource_type là FIELD ──────────────────────────────────────
    resource_type = fields.Selection([
        ('material', 'Vật liệu'),
        ('material_aux', 'Vật liệu phụ'),
        ('labor', 'Nhân công'),
        ('machine', 'Máy thi công'),
        ('subcontract', 'Thầu phụ'),
    ], string='Loại tài nguyên', required=True, index=True)

    categ_id = fields.Many2one(
        'rp.resource.category', string='Nhóm', index=True)

    # tiêu chuẩn MÌNH YÊU CẦU (khác với tiêu chuẩn NCC KHAI ở dòng giá)
    standard_edition_id = fields.Many2one(
        'rp.standard.edition', string='Tiêu chuẩn yêu cầu',
        help='Tiêu chuẩn mình YÊU CẦU cho tài nguyên này (vd PCB30 theo '
             'TCVN 6260:2020). So với tiêu chuẩn nhà cung cấp KHAI ở dòng '
             'giá để bắt lệch.')

    # cầu nối theo loại (§4.3): vật tư/nhân công → product; máy → re_asset
    product_id = fields.Many2one(
        'product.product', string='Sản phẩm liên kết',
        help='Nối tới product.product cho vật tư/nhân công — để đối chiếu '
             'dự toán với thực chi (hoá đơn mua). Máy KHÔNG nối product vì '
             'chi phí máy đến từ thuê/khấu hao, không qua hoá đơn mua.')

    note = fields.Text(string='Ghi chú')
    active = fields.Boolean(default=True)

    _uniq_code = models.Constraint(
        'unique(code)', 'Mã tài nguyên đã tồn tại — mỗi mã chỉ khai một lần.')

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for r in self:
            r.display_name = '[%s] %s' % (r.code, r.name) if r.code else r.name
