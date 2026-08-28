# -*- coding: utf-8 -*-
"""Nối hồ sơ dự thầu vào THƯ VIỆN ĐỊNH MỨC và CÔNG BỐ GIÁ.

Trước file này, tầng chi phí của dòng BoQ phải gõ tay từng dòng: mở
dòng BoQ, thêm từng vật tư / nhân công / ca máy, gõ định mức, gõ giá.
Bộ định mức quốc gia và bảng công bố giá của tỉnh đã nằm sẵn trong
`rp_cost_library` (`rp.norm`, `rp.price.publication`) nhưng không có
đường nào đi từ đó sang hồ sơ thầu — hai kho dữ liệu đứng cạnh nhau mà
không chạm nhau.

ĐƯỜNG ĐI GIỜ LÀ:

    Hồ sơ  ──chọn──→  Bộ định mức  +  Công bố giá   (một lần cho cả gói)
      │
    Dòng BoQ ──chọn──→ Định mức AC.32140
      │
      └─ bấm "Lấy chi phí từ định mức"
             │
             ├ hao phí   ← rp.norm.line   (0,56 công/1m³…)
             └ đơn giá   ← Bảng giá gói thầu › Công bố giá › Thư viện

BA TẦNG GIÁ, TRA THEO ĐÚNG THỨ TỰ ƯU TIÊN. Giá riêng của gói thắng giá
công bố, giá công bố thắng thư viện công ty. Lý do: giá riêng của gói là
thứ nhà thầu đã đàm phán được với nhà cung cấp cho ĐÚNG gói này — nó gần
sự thật hơn mọi bảng công bố. Công bố giá đứng trên thư viện công ty vì
nó gắn với một văn bản có số, có ngày, cãi được khi bị hỏi.

KHÔNG ĐOÁN VAT. `rp.price.line` cố ý có trạng thái "KHÔNG RÕ" cho VAT
(xem `rp_price.py` — bảng công bố thật hay ghi VAT trong tên nhóm, bằng
văn xuôi). Khi kéo giá về mà gặp dòng không rõ VAT thì ĐẾM và BÁO ra,
chứ không im lặng coi như đã gồm hoặc chưa gồm. Lệch 8-10% trên toàn bộ
vật liệu là đủ để thắng nhầm hoặc trượt oan một gói thầu.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class RpBidNormSource(models.Model):
    _inherit = 'rp.bid'

    norm_set_id = fields.Many2one(
        'rp.norm.set', string='Bộ định mức áp dụng',
        ondelete='restrict', index=True, tracking=True,
        help='Bộ định mức dùng cho cả gói này (VD TT 12/2021, TT 38/2026). '
             'Chọn ở đây rồi thì ô "Định mức" của từng dòng BoQ chỉ đổ ra '
             'mã hiệu thuộc bộ này — bộ định mức có hàng nghìn mã, không '
             'lọc thì chọn nhầm bộ là chuyện sớm muộn.')
    price_publication_id = fields.Many2one(
        'rp.price.publication', string='Công bố giá áp dụng',
        ondelete='restrict', index=True, tracking=True,
        help='Văn bản công bố giá dùng làm mốc cho gói này. Có số, có '
             'ngày — khi bị hỏi "giá này ở đâu ra" thì đây là câu trả lời.')
    price_region_id = fields.Many2one(
        'rp.price.region', string='Vùng giá',
        ondelete='restrict',
        help='Chỉ ảnh hưởng nhân công và ca máy: cùng một tỉnh nhưng khác '
             'vùng thì khác đơn giá.')
    price_publication_stale = fields.Boolean(
        string='Công bố giá đã bị thay',
        related='price_publication_id.is_superseded')

    # ==================================================================
    def _resolve_unit_price(self, resource):
        """Đơn giá của một tài nguyên cho hồ sơ này.

        Trả về `(giá, nguồn, vat_chắc_chắn)`. `vat_chắc_chắn` chỉ False
        khi giá lấy từ một dòng công bố giá không ghi rõ VAT — người
        bấm nút phải biết điều đó, xem docstring đầu file.
        """
        self.ensure_one()
        if not resource:
            return 0.0, False, True

        # ① Giá riêng của gói — đã đàm phán cho đúng gói này.
        own = self.price_ids.filtered(
            lambda p: p.resource_id == resource)[:1]
        if own and own.price:
            return own.price, 'bid', True

        Line = self.env['rp.price.line']
        # ② Công bố giá đã chọn. Ưu tiên dòng đúng vùng, vì nhân công và
        #    ca máy khác nhau theo vùng ngay trong một tỉnh.
        if self.price_publication_id:
            base = [('publication_id', '=', self.price_publication_id.id),
                    ('resource_id', '=', resource.id)]
            found = False
            if self.price_region_id:
                found = Line.search(
                    base + [('region_id', '=', self.price_region_id.id)],
                    order='id desc', limit=1)
            if not found:
                found = Line.search(base, order='id desc', limit=1)
            if found:
                return found.price, 'publication', found.vat_certain

        # ③ Thư viện công ty — dòng giá mới nhất bất kể công bố nào.
        lib = Line.search([('resource_id', '=', resource.id)],
                          order='id desc', limit=1)
        if lib:
            return lib.price, 'library', lib.vat_certain
        return 0.0, False, True

    def action_pull_norm_all(self):
        """Bung định mức cho MỌI dòng BoQ đã chọn định mức trong hồ sơ."""
        self.ensure_one()
        lines = self.line_ids.filtered('norm_id')
        if not lines:
            raise UserError(_(
                'Chưa dòng BoQ nào chọn định mức. Mở một dòng BoQ (mũi tên '
                'cuối dòng), chọn ô "Định mức", rồi quay lại bấm nút này.'))
        return lines.action_pull_norm()


class RpBidBoqLineNorm(models.Model):
    _inherit = 'rp.bid.boq.line'

    norm_set_id = fields.Many2one(
        related='bid_id.norm_set_id', string='Bộ định mức của hồ sơ')
    norm_id = fields.Many2one(
        'rp.norm', string='Định mức', ondelete='restrict', index=True,
        help='Mã hiệu trong thư viện định mức. Chọn xong bấm "Lấy chi phí '
             'từ định mức" để bung hao phí thành các dòng chi phí, đơn giá '
             'lấy theo công bố giá đã chọn ở hồ sơ.\n'
             'Để trống vẫn làm việc bình thường — gõ tay "Mã định mức" và '
             'tự khai chi phí, đúng như trước.')
    norm_line_count = fields.Integer(
        string='Số hao phí trong định mức', compute='_compute_norm_lines')
    norm_pulled = fields.Boolean(
        string='Đã lấy chi phí từ định mức', compute='_compute_norm_lines',
        help='Mọi hao phí của định mức đều đã có dòng chi phí tương ứng.')

    @api.depends('norm_id', 'norm_id.line_ids',
                 'resource_line_ids.resource_id')
    def _compute_norm_lines(self):
        for rec in self:
            need = rec.norm_id.line_ids.mapped('resource_id')
            rec.norm_line_count = len(need)
            have = rec.resource_line_ids.mapped('resource_id')
            rec.norm_pulled = bool(need) and not (need - have)

    @api.onchange('norm_id')
    def _onchange_norm_id(self):
        """Chọn định mức thì điền mã hiệu và tên công tác.

        Nội dung công việc chỉ điền khi đang TRỐNG: tên trong bộ định mức
        là tên chuẩn của công tác, còn nội dung trong hồ sơ thầu phải
        giữ theo cách bên mời thầu diễn đạt.
        """
        if not self.norm_id:
            return
        self.norm_code = self.norm_id.code
        if not self.description:
            self.description = self.norm_id.name

    @api.constrains('norm_id')
    def _check_norm_set(self):
        for rec in self:
            if (rec.norm_id and rec.norm_set_id
                    and rec.norm_id.set_id != rec.norm_set_id):
                raise ValidationError(_(
                    'Định mức "%(norm)s" thuộc bộ %(has)s, trong khi hồ sơ '
                    'đang áp dụng bộ %(want)s. Trộn hai bộ định mức trong '
                    'một hồ sơ thì hao phí không so sánh được với nhau.',
                    norm=rec.norm_id.display_name,
                    has=rec.norm_id.set_id.display_name,
                    want=rec.norm_set_id.display_name))

    def action_pull_norm(self):
        """Bung hao phí của định mức thành dòng chi phí của dòng BoQ.

        CHỈ THÊM CÁI CÒN THIẾU, không xoá và không ghi đè. Dòng chi phí
        đang có thường là thứ người làm giá đã sửa tay cho đúng thực tế
        thi công của mình — định mức nhà nước là mức trung bình, không
        phải mức của một nhà thầu cụ thể. Ghi đè nghĩa là mỗi lần lỡ tay
        bấm nút là mất hết phần hiệu chỉnh đó.
        """
        RL = self.env['rp.bid.resource.line']
        vals_list = []
        skipped = 0
        no_price = 0
        vat_unknown = 0
        for rec in self:
            if not rec.norm_id:
                raise UserError(_(
                    'Dòng BoQ "%s" chưa chọn định mức.', rec.display_name))
            have = set(rec.resource_line_ids.mapped('resource_id').ids)
            seq = 10
            for nl in rec.norm_id.line_ids:
                if nl.resource_id.id in have:
                    skipped += 1
                    continue
                price, _src, vat_ok = rec.bid_id._resolve_unit_price(
                    nl.resource_id)
                # Dòng khai theo % ("máy khác 5%") không có đơn giá riêng —
                # xem `rp.bid.resource.line._compute_amount`.
                if nl.is_percent:
                    price = 0.0
                elif not price:
                    no_price += 1
                elif not vat_ok:
                    vat_unknown += 1
                vals_list.append({
                    'line_id': rec.id,
                    'sequence': seq,
                    'resource_id': nl.resource_id.id,
                    'norm_qty': nl.quantity,
                    'is_percent': nl.is_percent,
                    'unit_price': price,
                })
                seq += 10
        if vals_list:
            RL.create(vals_list)

        msg = _('Đã thêm %s dòng chi phí.', len(vals_list))
        if skipped:
            msg += _(' Bỏ qua %s dòng đã có.', skipped)
        if no_price:
            msg += _(' %s dòng CHƯA CÓ GIÁ — kiểm ở tab Bảng giá gói thầu.',
                     no_price)
        if vat_unknown:
            msg += _(' %s dòng lấy giá công bố KHÔNG RÕ VAT — phải xác nhận '
                     'trước khi chào.', vat_unknown)
        return self.env['rp.bid']._notify(msg)
