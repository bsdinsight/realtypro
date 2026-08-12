# -*- coding: utf-8 -*-
"""Master tiêu chuẩn kỹ thuật — §4.4 của vn_cost_data_pattern.md.

Vì sao cần model riêng thay vì một ô text:
- Cùng "Xi măng bao PCB30", Thành Thắng khai theo TCVN 6260:**2020**, còn
  Vicem Bút Sơn khai theo TCVN 6260:**2009** (bản đã bị 2020 thay) — mà lại
  đắt hơn 34%. Chỉ khi tiêu chuẩn CÓ PHIÊN BẢN + QUAN HỆ THAY THẾ thì hệ
  thống mới tự hỏi "bản 2009 còn hiệu lực không". Ô text thì chịu.
- TCVN (tự nguyện) ≠ QCVN (BẮT BUỘC) ≠ TCCS (doanh nghiệp tự công bố) — khác
  nhau về PHÁP LÝ, không phải phân loại. `is_mandatory` phải tách bạch được.
- ASTM/JIS/GB/BS/DIN là tiêu chuẩn QUỐC GIA của nước khác, KHÔNG phải "quốc
  tế". Nên dùng `country_id`, đừng dùng selection VN/Quốc tế.
"""
from odoo import _, api, fields, models


class RpStandard(models.Model):
    _name = 'rp.standard'
    _description = 'Tiêu chuẩn / Quy chuẩn kỹ thuật'
    _order = 'code'

    code = fields.Char(string='Ký hiệu', required=True, index=True,
                       help='VD: TCVN 6260, QCVN 16, ASTM C91')
    name = fields.Char(string='Tên', required=True, translate=True)
    standard_type = fields.Selection([
        ('tcvn', 'Tiêu chuẩn quốc gia (TCVN)'),
        ('qcvn', 'Quy chuẩn quốc gia (QCVN) — bắt buộc'),
        ('tccs', 'Tiêu chuẩn cơ sở (TCCS)'),
        ('foreign', 'Tiêu chuẩn nước ngoài / quốc tế'),
    ], string='Loại', required=True, default='tcvn')
    country_id = fields.Many2one(
        'res.country', string='Quốc gia ban hành',
        help='Bỏ trống nếu là tiêu chuẩn quốc tế (ISO/IEC). ASTM=Hoa Kỳ, '
             'JIS=Nhật, GB=Trung Quốc — đều là tiêu chuẩn quốc gia.')
    issuer = fields.Char(
        string='Cơ quan ban hành',
        help='VD: Bộ KHCN (TCVN/QCVN), ASTM International, ISO')
    is_mandatory = fields.Boolean(
        string='Bắt buộc áp dụng', compute='_compute_is_mandatory',
        store=True,
        help='Quy chuẩn (QCVN) = bắt buộc. Tiêu chuẩn (TCVN/TCCS) = tự '
             'nguyện. Đây là khác biệt pháp lý, quyết định vật liệu có được '
             'dùng cho công trình vốn nhà nước hay không.')
    edition_ids = fields.One2many(
        'rp.standard.edition', 'standard_id', string='Các phiên bản')
    edition_count = fields.Integer(
        string='Số phiên bản', compute='_compute_edition_count')
    note = fields.Text(string='Ghi chú')
    active = fields.Boolean(default=True)

    _uniq_code = models.Constraint(
        'unique(code)', 'Ký hiệu tiêu chuẩn đã tồn tại — mỗi ký hiệu chỉ khai một lần.')

    @api.depends('standard_type')
    def _compute_is_mandatory(self):
        for r in self:
            r.is_mandatory = r.standard_type == 'qcvn'

    @api.depends('edition_ids')
    def _compute_edition_count(self):
        for r in self:
            r.edition_count = len(r.edition_ids)

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for r in self:
            r.display_name = '%s — %s' % (r.code or '', r.name or '') \
                if r.name else (r.code or '')


class RpStandardEdition(models.Model):
    _name = 'rp.standard.edition'
    _description = 'Phiên bản tiêu chuẩn'
    _order = 'standard_id, year desc'

    standard_id = fields.Many2one(
        'rp.standard', string='Tiêu chuẩn', required=True,
        ondelete='cascade', index=True)
    year = fields.Integer(string='Năm ban hành', required=True,
                          help='VD: TCVN 6260:2020 → năm = 2020')
    effective_date = fields.Date(string='Ngày hiệu lực')
    superseded_by_id = fields.Many2one(
        'rp.standard.edition', string='Bị thay thế bởi',
        help='Điền khi phiên bản này đã bị một phiên bản mới thay. Đây là '
             'chỗ để hệ thống cảnh báo "nhà cung cấp đang chào theo bản đã '
             'bị thay".')
    is_superseded = fields.Boolean(
        string='Đã bị thay', compute='_compute_is_superseded', store=True)
    note = fields.Char(string='Ghi chú')
    active = fields.Boolean(default=True)

    _uniq_std_year = models.Constraint(
        'unique(standard_id, year)',
        'Mỗi tiêu chuẩn chỉ có một phiên bản cho mỗi năm.')

    @api.depends('superseded_by_id')
    def _compute_is_superseded(self):
        for r in self:
            r.is_superseded = bool(r.superseded_by_id)

    @api.depends('standard_id.code', 'year')
    def _compute_display_name(self):
        for r in self:
            r.display_name = '%s:%s' % (r.standard_id.code or '', r.year or '')
