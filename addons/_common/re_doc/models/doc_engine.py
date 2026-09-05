# -*- coding: utf-8 -*-
"""Doc Template — engine render Word mail-merge (docxtpl).

Tầng A: nhận template .docx có placeholder Jinja2 + 1 record → xuất
docx (hoặc PDF nếu có LibreOffice). Stateless, dùng được cho mọi model.
"""
import base64
import logging
import os
import subprocess
import sys
import tempfile
from io import BytesIO

from odoo import _, api, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Thư viện cài rời trong addons path (host pip --target), giống cách
# rs_operations nạp OpenCV cho Stacking Plan.
_PYLIBS = '/mnt/community/_common/_pylibs'
if os.path.isdir(_PYLIBS) and _PYLIBS not in sys.path:
    sys.path.append(_PYLIBS)

MAX_DEPTH = 3
SKIP_PREFIXES = ('message_', 'activity_', 'website_message')
SKIP_FIELDS = {
    'create_uid', 'create_date', 'write_uid', 'write_date', '__last_update',
    'access_token', 'access_url', 'access_warning', 'has_message',
    'my_activity_date_deadline', 'rating_ids', 'display_name',
}


def _vn_money(value, suffix='đ'):
    try:
        n = float(value or 0)
    except (TypeError, ValueError):
        return ''
    s = f'{n:,.0f}'.replace(',', '.')
    return f'{s} {suffix}'.strip()


def _vn_num(value, digits=2):
    try:
        n = float(value or 0)
    except (TypeError, ValueError):
        return ''
    s = f'{n:,.{digits}f}'
    return s.replace(',', '@').replace('.', ',').replace('@', '.')


def _vn_date(value, fmt='%d/%m/%Y'):
    if not value:
        return ''
    try:
        return value.strftime(fmt)
    except AttributeError:
        return str(value)


def _vn_date_full(value):
    if not value:
        return ''
    try:
        return 'ngày %02d tháng %02d năm %d' % (
            value.day, value.month, value.year)
    except AttributeError:
        return str(value)


class ReDocEngine(models.AbstractModel):
    _name = 're.doc.engine'
    _description = 'Doc Template Render Engine'

    # ------------------------------------------------------------------
    # Context: recordset ORM → dict lồng nhau (docxtpl không ORM-load được)
    # ------------------------------------------------------------------
    @api.model
    def _value_to_ctx(self, record, fname, field, depth):
        value = record[fname]
        ftype = field.type
        if ftype in ('many2one',):
            if not value:
                return ''
            if depth >= MAX_DEPTH:
                return value.display_name or ''
            return self._record_to_ctx(value[:1], depth + 1)
        if ftype in ('one2many', 'many2many'):
            if depth >= MAX_DEPTH:
                return [r.display_name for r in value]
            return [self._record_to_ctx(r, depth + 1) for r in value]
        if ftype == 'selection':
            if not value:
                return ''
            try:
                labels = dict(field._description_selection(self.env))
            except Exception:
                labels = {}
            return labels.get(value, value)
        if ftype in ('date', 'datetime'):
            return value or ''
        if ftype == 'boolean':
            return value
        if value is False or value is None:
            return ''
        return value

    @api.model
    def _record_to_ctx(self, record, depth=0):
        """Một record → dict. Trả '' cho giá trị rỗng để không in 'False'."""
        if not record:
            return {}
        record = record[:1]
        data = {'id': record.id, 'display_name': record.display_name or ''}
        for fname, field in record._fields.items():
            if fname in SKIP_FIELDS or fname.startswith(SKIP_PREFIXES):
                continue
            if field.type in ('binary', 'image', 'html'):
                if field.type == 'html':
                    data[fname] = record[fname] or ''
                continue
            try:
                data[fname] = self._value_to_ctx(record, fname, field, depth)
            except Exception:            # field lỗi không được chặn cả bản in
                data[fname] = ''
        return data

    @api.model
    def _build_context(self, record):
        company = self.env.company
        today = self.env['ir.fields.converter'] and None  # noqa: giữ import gọn
        from datetime import date
        today = date.today()
        return {
            'record': self._record_to_ctx(record),
            '_orm': record,
            'today': _vn_date(today),
            'today_full': _vn_date_full(today),
            'company': self._record_to_ctx(company, depth=MAX_DEPTH - 1),
            'user': {
                'name': self.env.user.name or '',
                'login': self.env.user.login or '',
                'phone': self.env.user.partner_id.phone or '',
                'email': self.env.user.email or '',
            },
        }

    @api.model
    def _jinja_env(self):
        try:
            from jinja2 import Environment
        except ImportError:
            raise UserError(_('Thiếu thư viện jinja2 trong container Odoo.'))
        env = Environment()
        env.filters['money'] = _vn_money
        env.filters['num'] = _vn_num
        env.filters['date'] = _vn_date
        env.filters['date_full'] = _vn_date_full
        return env

    # ------------------------------------------------------------------
    # Render
    # ------------------------------------------------------------------
    @api.model
    def render_template(self, template, record):
        """Trả (bytes, filename). PDF nếu bật và có LibreOffice."""
        if not template.docx_file:
            raise UserError(_(
                'Mẫu "%s" chưa có tệp Word (.docx).') % template.name)
        try:
            from docxtpl import DocxTemplate
        except ImportError:
            raise UserError(_(
                'Chưa cài thư viện docxtpl trong môi trường Odoo. '
                'Cài bằng: pip install --target %s docxtpl python-docx')
                % _PYLIBS)

        raw = base64.b64decode(template.docx_file)
        doc = DocxTemplate(BytesIO(raw))
        ctx = self._build_context(record)
        try:
            doc.render(ctx, jinja_env=self._jinja_env())
        except Exception as exc:
            raise UserError(_(
                'Lỗi khi trộn dữ liệu vào mẫu "%s":\n\n%s\n\n'
                'Kiểm tra lại placeholder trong file Word.') % (
                template.name, exc))
        out = BytesIO()
        doc.save(out)
        content = out.getvalue()

        base_name = (record.display_name or 'tai-lieu').replace('/', '-')
        filename = '%s - %s.docx' % (template.name, base_name)
        if template.output_pdf:
            pdf = self._docx_to_pdf(content)
            if pdf:
                return pdf, filename[:-5] + '.pdf'
            _logger.warning(
                'Doc Template: không chuyển được PDF (thiếu LibreOffice), '
                'trả về .docx')
        return content, filename

    @api.model
    def _docx_to_pdf(self, content):
        """docx → pdf bằng LibreOffice. None nếu không có soffice."""
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, 'in.docx')
            with open(src, 'wb') as fh:
                fh.write(content)
            try:
                subprocess.run(
                    ['soffice', '--headless', '--norestore',
                     '--convert-to', 'pdf', '--outdir', tmp, src],
                    check=True, capture_output=True, timeout=120)
            except (FileNotFoundError, subprocess.SubprocessError) as exc:
                _logger.warning('Doc Template: soffice lỗi: %s', exc)
                return None
            pdf = os.path.join(tmp, 'in.pdf')
            if not os.path.exists(pdf):
                return None
            with open(pdf, 'rb') as fh:
                return fh.read()

    # ------------------------------------------------------------------
    # Curated placeholders — dùng cho cheatsheet (tầng A) và sidebar
    # OnlyOffice (tầng B) sau này
    # ------------------------------------------------------------------
    @api.model
    def curated_groups(self, model_name):
        """Nhóm placeholder nghiệp vụ theo model đích."""
        common_buyer = [
            ('Họ tên bên mua', '{{ record.partner_id.name }}'),
            ('Số CMND/CCCD', '{{ record.partner_id.vn_national_id }}'),
            ('Ngày cấp', '{{ record.partner_id.vn_national_id_issue_date|date }}'),
            ('Nơi cấp', '{{ record.partner_id.vn_national_id_issue_place }}'),
            ('Số hộ chiếu', '{{ record.partner_id.passport_number }}'),
            ('Địa chỉ thường trú', '{{ record.partner_id.vn_permanent_address }}'),
            ('Điện thoại', '{{ record.partner_id.phone }}'),
            ('Điện thoại phụ', '{{ record.partner_id.phone_secondary }}'),
            ('Email', '{{ record.partner_id.email }}'),
            ('Mã số thuế', '{{ record.partner_id.vn_tax_code }}'),
        ]
        seller = [
            ('Tên chủ đầu tư', '{{ company.name }}'),
            ('Mã số thuế CĐT', '{{ company.vat }}'),
            ('Địa chỉ CĐT', '{{ company.street }}'),
            ('Điện thoại CĐT', '{{ company.phone }}'),
            ('Email CĐT', '{{ company.email }}'),
            ('Người lập', '{{ user.name }}'),
            ('Ngày in (dd/mm/yyyy)', '{{ today }}'),
            ('Ngày in (ngày… tháng… năm…)', '{{ today_full }}'),
        ]
        product = [
            ('Dự án', '{{ record.project_id.name }}'),
            ('Mã căn / lô', '{{ record.unit_id.unit_code }}'),
            ('Loại sản phẩm', '{{ record.unit_id.unit_type_id.name }}'),
            ('Diện tích thông thủy', '{{ record.unit_id.area_net|num }} m²'),
            ('Diện tích tim tường', '{{ record.unit_id.area_gross|num }} m²'),
            ('Diện tích đất', '{{ record.unit_id.area_land|num }} m²'),
            ('Diện tích xây', '{{ record.unit_id.area_construction|num }} m²'),
            ('Hướng', '{{ record.unit_id.direction }}'),
            ('Tầng', '{{ record.unit_id.floor_id.name }}'),
        ]
        pricing_split = [
            ('Diện tích đất', '{{ record.area_land|num }} m²'),
            ('Đơn giá đất', '{{ record.price_per_m2_land|money }}'),
            ('Giá gốc phần đất', '{{ record.land_total|money }}'),
            ('Chiết khấu đất', '{{ record.discount_land|money }}'),
            ('Tiền đất trước VAT', '{{ record.land_before_vat|money }}'),
            ('VAT đất', '{{ record.vat_land|money }}'),
            ('Tiền đất sau VAT', '{{ record.land_after_vat|money }}'),
            ('Diện tích xây', '{{ record.area_construction|num }} m²'),
            ('Đơn giá xây', '{{ record.price_per_m2_construction|money }}'),
            ('Giá gốc phần xây', '{{ record.construction_total|money }}'),
            ('Chiết khấu xây', '{{ record.discount_construction|money }}'),
            ('Tiền xây trước VAT', '{{ record.construction_before_vat|money }}'),
            ('VAT xây', '{{ record.vat_construction|money }}'),
            ('Tiền xây sau VAT', '{{ record.construction_after_vat|money }}'),
        ]
        pricing_total = [
            ('Giá niêm yết', '{{ record.listed_price|money }}'),
            ('Chiết khấu', '{{ record.discount|money }}'),
            ('Khuyến mãi', '{{ record.promotion|money }}'),
            ('Giá bán trước VAT', '{{ record.net_selling_price|money }}'),
            ('VAT', '{{ record.vat_amount_calc|money }}'),
            ('Giá bán sau VAT', '{{ record.net_selling_price_after_vat|money }}'),
            ('Phí bảo trì', '{{ record.maintenance_fee_calc|money }}'),
            ('Tổng thanh toán', '{{ record.total_amount|money }}'),
        ]
        groups = {
            're.sale.contract': [
                ('📋 Hợp đồng', [
                    ('Số hợp đồng', '{{ record.name }}'),
                    ('Ngày hợp đồng', '{{ record.contract_date|date }}'),
                    ('Ngày hợp đồng (dạng chữ)',
                     '{{ record.contract_date|date_full }}'),
                    ('Ngày ký', '{{ record.signed_date|date }}'),
                    ('Giá trị hợp đồng', '{{ record.contract_amount|money }}'),
                    ('Tiền cọc', '{{ record.deposit_amount|money }}'),
                    ('Cọc đã thu', '{{ record.deposit_paid|money }}'),
                    ('Tổng đã thanh toán', '{{ record.amount_paid_total|money }}'),
                    ('Còn phải thu', '{{ record.amount_residual|money }}'),
                    ('Trạng thái', '{{ record.state }}'),
                ]),
                ('👤 Bên mua', common_buyer),
                ('🏦 Bên bán (Chủ đầu tư)', seller),
                ('🏢 Dự án & Sản phẩm', product),
                ('💰 Giá — tách Đất / Xây', pricing_split),
                ('💰 Giá — tổng hợp', pricing_total),
                ('📅 Lịch thanh toán (vòng lặp)', [
                    ('Bảng lịch TỔNG HỢP — đặt trong 1 dòng bảng Word',
                     '{%tr for l in record.installment_combined_ids %}'),
                    ('… tên đợt', '{{ l.name }}'),
                    ('… thành phần', '{{ l.component }}'),
                    ('… ngày đến hạn', '{{ l.due_date|date }}'),
                    ('… tỷ lệ %', '{{ l.percent_of_price|num }}%'),
                    ('… số tiền', '{{ l.amount|money }}'),
                    ('… đã thanh toán', '{{ l.amount_paid|money }}'),
                    ('… còn lại', '{{ l.balance|money }}'),
                    ('Kết thúc vòng lặp', '{%tr endfor %}'),
                    ('(Bộ chi tiết Đất)',
                     '{%tr for l in record.installment_land_ids %}'),
                    ('(Bộ chi tiết Xây)',
                     '{%tr for l in record.installment_construction_ids %}'),
                ]),
                ('👥 Đồng sở hữu (vòng lặp)', [
                    ('Mở vòng lặp', '{%tr for c in record.coowner_ids %}'),
                    ('… họ tên', '{{ c.partner_id.name }}'),
                    ('… CMND/CCCD', '{{ c.partner_id.vn_national_id }}'),
                    ('… quan hệ', '{{ c.relationship }}'),
                    ('… tỷ lệ sở hữu', '{{ c.ownership_pct|num }}%'),
                    ('Kết thúc vòng lặp', '{%tr endfor %}'),
                ]),
            ],
            're.sale.deposit': [
                ('📋 Đặt cọc', [
                    ('Số phiếu cọc', '{{ record.name }}'),
                    ('Ngày đặt cọc', '{{ record.deposit_date|date }}'),
                    ('Ngày đặt cọc (dạng chữ)',
                     '{{ record.deposit_date|date_full }}'),
                    ('Số tiền cọc', '{{ record.deposit_amount|money }}'),
                    ('Đã thu', '{{ record.amount_paid|money }}'),
                    ('Trạng thái', '{{ record.state }}'),
                ]),
                ('👤 Bên mua', common_buyer),
                ('🏦 Bên bán (Chủ đầu tư)', seller),
                ('🏢 Dự án & Sản phẩm', product),
                ('💰 Giá — tách Đất / Xây', pricing_split),
                ('💰 Giá — tổng hợp', pricing_total),
                ('📅 Lịch thanh toán (vòng lặp)', [
                    ('Mở vòng lặp (tổng hợp)',
                     '{%tr for l in record.installment_combined_ids %}'),
                    ('… tên đợt', '{{ l.name }}'),
                    ('… ngày đến hạn', '{{ l.due_date|date }}'),
                    ('… số tiền', '{{ l.amount|money }}'),
                    ('Kết thúc vòng lặp', '{%tr endfor %}'),
                ]),
                ('👥 Đồng sở hữu (vòng lặp)', [
                    ('Mở vòng lặp', '{%tr for c in record.coowner_ids %}'),
                    ('… họ tên', '{{ c.partner_id.name }}'),
                    ('… tỷ lệ sở hữu', '{{ c.ownership_pct|num }}%'),
                    ('Kết thúc vòng lặp', '{%tr endfor %}'),
                ]),
            ],
            're.sale.addendum': [
                ('📋 Phụ lục', [
                    ('Số phụ lục', '{{ record.name }}'),
                    ('Loại phụ lục', '{{ record.addendum_type }}'),
                    ('Ngày lập', '{{ record.date|date }}'),
                    ('Ngày lập (dạng chữ)', '{{ record.date|date_full }}'),
                    ('Ngày hiệu lực', '{{ record.effective_date|date }}'),
                    ('Diễn giải', '{{ record.description }}'),
                ]),
                ('🔗 Hợp đồng gốc', [
                    ('Số hợp đồng', '{{ record.contract_id.name }}'),
                    ('Ngày hợp đồng',
                     '{{ record.contract_id.contract_date|date }}'),
                    ('Ngày ký', '{{ record.contract_id.signed_date|date }}'),
                    ('Giá trị hợp đồng',
                     '{{ record.contract_id.contract_amount|money }}'),
                ]),
                ('👤 Bên mua', common_buyer),
                ('🏦 Bên bán (Chủ đầu tư)', seller),
                ('🏢 Dự án & Sản phẩm', product),
                ('🔄 Nội dung thay đổi — diện tích / đơn giá / chiết khấu', [
                    ('Diện tích cũ', '{{ record.old_area|num }} m²'),
                    ('Diện tích mới', '{{ record.new_area|num }} m²'),
                    ('Đơn giá cũ', '{{ record.old_price|money }}'),
                    ('Đơn giá mới', '{{ record.new_price|money }}'),
                    ('Chiết khấu cũ', '{{ record.old_discount|money }}'),
                    ('Chiết khấu mới', '{{ record.new_discount|money }}'),
                    ('Nội dung đổi tiến độ', '{{ record.installment_note }}'),
                ]),
                ('🔄 Thay đổi thông tin khách hàng (trước → sau)', [
                    ('Địa chỉ thường trú cũ',
                     '{{ record.old_permanent_address }}'),
                    ('Địa chỉ thường trú mới',
                     '{{ record.new_permanent_address }}'),
                    ('Điện thoại cũ', '{{ record.old_phone }}'),
                    ('Điện thoại mới', '{{ record.new_phone }}'),
                    ('CMND/CCCD cũ', '{{ record.old_national_id }}'),
                    ('CMND/CCCD mới', '{{ record.new_national_id }}'),
                    ('Ngày cấp cũ', '{{ record.old_id_issue_date|date }}'),
                    ('Ngày cấp mới', '{{ record.new_id_issue_date|date }}'),
                    ('Nơi cấp cũ', '{{ record.old_id_issue_place }}'),
                    ('Nơi cấp mới', '{{ record.new_id_issue_place }}'),
                    ('Hộ chiếu cũ', '{{ record.old_passport_number }}'),
                    ('Hộ chiếu mới', '{{ record.new_passport_number }}'),
                ]),
                ('👥 Đồng sở hữu sau phụ lục (vòng lặp)', [
                    ('Mở vòng lặp', '{%tr for c in record.coowner_ids %}'),
                    ('… họ tên', '{{ c.partner_id.name }}'),
                    ('… quan hệ', '{{ c.relationship }}'),
                    ('… tỷ lệ sở hữu', '{{ c.ownership_pct|num }}%'),
                    ('Kết thúc vòng lặp', '{%tr endfor %}'),
                ]),
            ],
            're.sale.booking': [
                ('📋 Giữ chỗ', [
                    ('Số phiếu', '{{ record.name }}'),
                    ('Ngày', '{{ record.booking_date|date }}'),
                    ('Tiền giữ chỗ', '{{ record.booking_fee|money }}'),
                    ('Đã thu', '{{ record.paid_amount|money }}'),
                ]),
                ('👤 Bên mua', common_buyer),
                ('🏦 Bên bán (Chủ đầu tư)', seller),
                ('🏢 Dự án & Sản phẩm', product),
            ],
            're.sale.receipt': [
                ('📋 Phiếu thu', [
                    ('Số phiếu', '{{ record.name }}'),
                    ('Ngày thu', '{{ record.date|date }}'),
                    ('Ngày thu (dạng chữ)', '{{ record.date|date_full }}'),
                    ('Loại phiếu', '{{ record.receipt_type }}'),
                    ('Hình thức', '{{ record.payment_method }}'),
                    ('Tổng tiền', '{{ record.amount_total|money }}'),
                    ('Diễn giải', '{{ record.note }}'),
                ]),
                ('👤 Người nộp', common_buyer),
                ('🏦 Đơn vị thu', seller),
                ('🏢 Dự án & Sản phẩm', product),
                ('💵 Chi tiết dòng tiền (vòng lặp)', [
                    ('Mở vòng lặp', '{%tr for l in record.line_ids %}'),
                    ('… loại tiền', '{{ l.payment_kind }}'),
                    ('… loại phí', '{{ l.fee_type }}'),
                    ('… diễn giải', '{{ l.description }}'),
                    ('… số tiền', '{{ l.amount|money }}'),
                    ('Kết thúc vòng lặp', '{%tr endfor %}'),
                ]),
            ],
        }
        return groups.get(model_name, [
            ('Trường cơ bản', [
                ('Tên hiển thị', '{{ record.display_name }}'),
                ('Ngày in', '{{ today }}'),
                ('Chủ đầu tư', '{{ company.name }}'),
            ]),
        ])
