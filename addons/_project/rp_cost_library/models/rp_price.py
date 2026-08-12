# -*- coding: utf-8 -*-
"""Công bố giá — §4.1-4.2 của vn_cost_data_pattern.md.

Đây là tầng GIÁ — nơi 20 chỗ phi lý trong §3 của spec biến thành field.
Nguyên tắc số 1: **một pattern không nói được "tôi không biết" thì nó sẽ
nói dối.** Nên `vat_included` và `price_basis` đều có trạng thái `unknown`,
và khi không rõ thì tổng giá TRẢ VỀ RỖNG, không đoán.

KHÔNG tồn tại "bảng giá tỉnh" — chỉ tồn tại CÔNG BỐ GIÁ. Bốn mô hình tỉnh
(Hà Nội tổng hợp · TP.HCM registry · Đà Nẵng hằng tháng · Bắc Ninh liên sở)
đều là trường hợp riêng của một khuôn.

Giá lưu MỘT số. `Tổng = Giá + VAT` suy ra được — lưu cả ba là mời sai lệch
vào nhà.
"""
from odoo import _, api, fields, models


class RpPriceRegion(models.Model):
    _name = 'rp.price.region'
    _description = 'Vùng giá (nhân công / ca máy)'
    _order = 'name'
    # C4: vùng KHÔNG bám cấp hành chính — HN theo phường/xã, HP có ĐẢO,
    # ĐN có đặc khu. Để tập hợp TỰ DO (sau nối bsd_vn_address frm.vn.ward).

    name = fields.Char(string='Tên vùng', required=True,
                       help='VD: Vùng I-KV1 (HN), Đảo Cát Bà (HP)')
    code = fields.Char(string='Mã')
    province_id = fields.Many2one('res.country.state', string='Tỉnh/TP')
    description = fields.Text(
        string='Phạm vi (nguyên văn)',
        help='Chép nguyên văn danh sách phường/xã/đặc khu như văn bản ghi — '
             'vì vùng không bám cấp hành chính nào.')
    active = fields.Boolean(default=True)


class RpPricePublication(models.Model):
    _name = 'rp.price.publication'
    _description = 'Công bố giá'
    _order = 'doc_date desc'

    name = fields.Char(compute='_compute_name', store=True)
    doc_no = fields.Char(string='Số văn bản', required=True,
                         help='VD: 3461/QĐ-SXD, TB 24594')
    doc_date = fields.Date(string='Ngày công bố', required=True)
    publisher_ids = fields.Many2many(
        'res.partner', string='Cơ quan công bố',
        help='M2M vì Bắc Ninh là LIÊN SỞ (Xây dựng + Tài chính) — hai pháp '
             'nhân, hai chữ ký, hai con dấu.')
    province_id = fields.Many2one('res.country.state', string='Tỉnh/TP')
    effective_from = fields.Date(string='Hiệu lực từ')
    effective_to = fields.Date(
        string='Hiệu lực đến',
        help='Bỏ TRỐNG = "đến khi có công bố mới" (TP.HCM, Bắc Ninh). '
             'Rỗng KHÔNG có nghĩa là vô hiệu.')
    superseded_by_id = fields.Many2one(
        'rp.price.publication', string='Bị thay bởi',
        help='VD: QĐ 3443 bị QĐ 3461 thay sau 3 NGÀY (tư vấn tổng hợp sai '
             'số liệu khảo sát). Cảnh báo khi dự toán dùng bản đã bị thay.')
    is_superseded = fields.Boolean(
        compute='_compute_is_superseded', store=True)
    source_type = fields.Selection([
        ('survey', 'Khảo sát (cơ quan/tư vấn)'),
        ('supplier_declared', 'Doanh nghiệp tự công bố'),
        ('mixed', 'Trộn (báo giá DN + khảo sát)'),
        ('local_gov_report', 'UBND phường/xã báo cáo'),
    ], string='Nguồn dữ liệu', default='survey',
        help='Ba nguồn cho cùng viên đá mà coi ngang nhau là sai. TP.HCM: '
             '8 phường báo cáo, chỉ 1 đúng quy định.')
    is_reference_only = fields.Boolean(
        string='Chỉ tham khảo', default=True, readonly=True,
        help='LUÔN True. Cả 4 tỉnh đều nói giá công bố chỉ để THAM KHẢO, '
             'CĐT tự chịu trách nhiệm. Không được trình bày như "giá đúng".')
    legal_basis = fields.Text(
        string='Căn cứ pháp lý',
        help='VD: Luật XD 135/2025, NĐ 206/2026. Lưu ý nhiều bảng còn dẫn '
             'căn cứ ĐÃ HẾT HIỆU LỰC (TP.HCM 8/7 vẫn dẫn NĐ 10/2021 đã bị '
             'NĐ 206 thay từ 1/7).')
    line_ids = fields.One2many(
        'rp.price.line', 'publication_id', string='Dòng giá')
    line_count = fields.Integer(compute='_compute_line_count')
    note = fields.Text(string='Ghi chú')
    active = fields.Boolean(default=True)

    _uniq_doc = models.Constraint(
        'unique(doc_no, doc_date)',
        'Công bố giá này đã có (trùng số + ngày).')

    @api.depends('doc_no', 'doc_date')
    def _compute_name(self):
        for r in self:
            r.name = '%s (%s)' % (r.doc_no or '', r.doc_date or '') \
                if r.doc_no else _('Công bố giá mới')

    @api.depends('superseded_by_id')
    def _compute_is_superseded(self):
        for r in self:
            r.is_superseded = bool(r.superseded_by_id)

    def _compute_line_count(self):
        for r in self:
            r.line_count = len(r.line_ids)


class RpPriceLine(models.Model):
    _name = 'rp.price.line'
    _description = 'Dòng giá công bố'
    _order = 'publication_id, resource_id'

    publication_id = fields.Many2one(
        'rp.price.publication', string='Công bố', required=True,
        ondelete='cascade', index=True)
    resource_id = fields.Many2one(
        'rp.resource', string='Tài nguyên', required=True, index=True)
    resource_type = fields.Selection(
        related='resource_id.resource_type', store=True)

    price = fields.Float(string='Giá', digits=(16, 2),
                         help='MỘT số. VAT và tổng SUY RA, không lưu riêng.')
    currency_id = fields.Many2one(
        'res.currency', string='Tiền tệ',
        default=lambda s: s.env.ref('base.VND', raise_if_not_found=False))

    # ── A1: VAT ba trạng thái ──
    vat_included = fields.Selection([
        ('yes', 'Đã gồm VAT'),
        ('no', 'Chưa gồm VAT'),
        ('unknown', 'KHÔNG RÕ'),
    ], string='VAT', default='unknown', required=True,
        help='HN: header ghi "chưa VAT" nhưng vài nhóm ghi "(đã bao gồm '
             'VAT)" TRONG TÊN NHÓM, văn xuôi. Không rõ thì KHÔNG được đoán.')
    vat_rate = fields.Float(string='Thuế suất %', default=8.0)

    # ── A2: mốc giá ──
    price_basis = fields.Selection([
        ('source', 'Tại nguồn (nhà máy)'),
        ('warehouse', 'Tại kho'),
        ('mine', 'Tại mỏ'),
        ('site_delivered', 'Đến chân công trình'),
        ('unknown', 'KHÔNG RÕ'),
    ], string='Mốc giá', default='unknown', required=True,
        help='ĐN công bố giá ĐẾN CHÂN CT (đã gồm cước) — cộng cước lên nữa '
             '= tính 2 lần. HN giá TẠI NGUỒN. Sai mốc lệch cả phần vận '
             'chuyển (cát đá 20-30%).')

    supplier_id = fields.Many2one(
        'res.partner', string='Nguồn cung',
        help='C1: cùng "cát đen" trong HN chênh 46% theo điểm bán. Giá gắn '
             'ĐIỂM BÁN, không gắn tỉnh. Đây cũng là nhà cung ứng trên Network.')
    region_id = fields.Many2one(
        'rp.price.region', string='Vùng',
        help='Chỉ cho nhân công/ca máy (giá đổi theo vùng trong tỉnh).')

    # tiêu chuẩn NHÀ CUNG CẤP KHAI (khác tiêu chuẩn resource YÊU CẦU)
    standard_edition_id = fields.Many2one(
        'rp.standard.edition', string='Tiêu chuẩn NCC khai',
        help='C3: so với tiêu chuẩn resource yêu cầu để bắt lệch — Bút Sơn '
             'khai PCB30 theo TCVN 6260:2009 (bản đã bị 2020 thay) mà đắt '
             'hơn 34%.')

    # ── B2: ngày công văn gốc ≠ ngày công bố ──
    source_doc = fields.Char(string='Công văn gốc')
    source_doc_date = fields.Date(
        string='Ngày công văn gốc',
        help='Tân Cang: CV 23/8/2024 nằm trong TB 6/2026 — lệch 22 THÁNG.')
    reliability = fields.Selection([
        ('high', 'Cao'),
        ('medium', 'Trung bình'),
        ('low', 'Thấp / cần kiểm'),
    ], string='Độ tin cậy', default='medium')
    note = fields.Char(string='Ghi chú')

    # ── Giá lưu MỘT số, VAT/tổng SUY RA (rỗng khi không rõ) ──
    price_ex_vat = fields.Float(
        string='Giá trước VAT', compute='_compute_vat_split',
        digits=(16, 2))
    price_inc_vat = fields.Float(
        string='Giá sau VAT', compute='_compute_vat_split', digits=(16, 2))
    vat_certain = fields.Boolean(
        string='VAT chắc chắn', compute='_compute_vat_split',
        help='False khi vat_included=unknown → không tính được tổng, và '
             'điều đó phải HIỆN RA, không giả vờ biết.')

    @api.depends('price', 'vat_included', 'vat_rate')
    def _compute_vat_split(self):
        for l in self:
            r = (l.vat_rate or 0.0) / 100.0
            if l.vat_included == 'yes':
                l.price_inc_vat = l.price
                l.price_ex_vat = l.price / (1 + r) if r else l.price
                l.vat_certain = True
            elif l.vat_included == 'no':
                l.price_ex_vat = l.price
                l.price_inc_vat = l.price * (1 + r)
                l.vat_certain = True
            else:  # unknown — KHÔNG đoán
                l.price_ex_vat = 0.0
                l.price_inc_vat = 0.0
                l.vat_certain = False
