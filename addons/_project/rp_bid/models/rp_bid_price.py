# -*- coding: utf-8 -*-
"""rp.bid.price — Bảng giá riêng của một hồ sơ dự thầu.

BA TẦNG GIÁ, VÀ VÌ SAO PHẢI ĐỦ BA:

    ① Thư viện công ty   (rp.price.line)      Item A = 15.000
    ② Bảng giá hồ sơ     (model này)          gói 1 = 16.000 · gói 2 = 16.500
    ③ Dòng chi phí       (rp.bid.resource.line.unit_price)   ngoại lệ từng đầu việc

Tầng ① là mặt bằng giá của công ty — thứ dùng để biết mình đang chào
cao hay thấp hơn chuẩn của chính mình.

Tầng ② là giá THỰC của gói thầu này: cùng một loại thép, gói ở Hà Nội
và gói ở Cà Mau khác giá vận chuyển; báo giá nhà cung cấp cũng chỉ có
hiệu lực cho gói đó. Giá ở đây **chỉ thuộc về hồ sơ này**, không đụng
tới thư viện công ty và không lan sang hồ sơ khác.

Tầng ③ giữ nguyên cho ngoại lệ ở một đầu việc lẻ.

GIÁ TRỊ THẬT NẰM Ở CHỖ SỬA MỘT LẦN, ĐỔI CẢ HỒ SƠ. Giá thép tăng giữa
kỳ làm giá: sửa một dòng ở đây rồi bấm áp dụng, toàn bộ dòng chi phí
dùng thép được cập nhật và giá dự thầu tính lại. Không có tầng này thì
phải dò tay trong 753 dòng chi phí.
"""
from odoo import _, api, fields, models


class RpBidPrice(models.Model):
    _name = 'rp.bid.price'
    _description = 'Bảng giá của hồ sơ dự thầu'
    _order = 'bid_id, resource_type, resource_id'

    bid_id = fields.Many2one(
        'rp.bid', string='Hồ sơ dự thầu', required=True,
        ondelete='cascade', index=True)
    project_id = fields.Many2one(
        related='bid_id.project_id', string='Dự án', store=True, index=True)
    package_id = fields.Many2one(
        related='bid_id.package_id', string='Gói thầu', store=True, index=True)
    currency_id = fields.Many2one(related='bid_id.currency_id')

    resource_id = fields.Many2one(
        'rp.resource', string='Item', required=True,
        ondelete='restrict', index=True)
    resource_type = fields.Selection(
        related='resource_id.resource_type', string='Loại',
        store=True, index=True)
    categ_id = fields.Many2one(
        related='resource_id.categ_id', string='Nhóm', store=True, index=True)
    uom_id = fields.Many2one(related='resource_id.uom_id', string='ĐVT')

    price = fields.Monetary(
        string='Giá cho gói này', currency_field='currency_id',
        help='Giá áp dụng RIÊNG cho hồ sơ dự thầu này. Không ghi đè thư '
             'viện công ty và không ảnh hưởng hồ sơ khác.')
    library_price = fields.Monetary(
        string='Giá thư viện công ty', currency_field='currency_id',
        compute='_compute_library', store=True,
        help='Giá mới nhất trong thư viện đơn giá của công ty. Để đối '
             'chiếu — nhà thầu chào theo giá mua thật của mình, còn thư '
             'viện là thước đo xem mình đang lệch mặt bằng bao nhiêu.')
    variance = fields.Monetary(
        string='Chênh với thư viện', currency_field='currency_id',
        compute='_compute_library', store=True)
    variance_pct = fields.Float(
        string='Chênh %', digits=(5, 1), compute='_compute_library',
        store=True)

    source = fields.Selection(
        [('library', 'Lấy từ thư viện công ty'),
         ('quote', 'Theo báo giá nhà cung cấp'),
         ('manual', 'Tự nhập'),
         ('imported', 'Theo file dự toán nhập vào')],
        string='Nguồn giá', default='manual', required=True, index=True,
        help='Ghi rõ giá từ đâu ra. Sau này bị hỏi "sao chào giá này" thì '
             'còn cơ sở trả lời.')
    note = fields.Char(string='Ghi chú')

    line_count = fields.Integer(
        string='Số dòng chi phí dùng', compute='_compute_usage')
    hp_levels = fields.Integer(
        string='Số mức giá trong chi phí', compute='_compute_usage')
    hp_min = fields.Monetary(
        string='Thấp nhất trong chi phí', currency_field='currency_id',
        compute='_compute_usage')
    hp_max = fields.Monetary(
        string='Cao nhất trong chi phí', currency_field='currency_id',
        compute='_compute_usage')
    # Không store: giá trị phụ thuộc các dòng chi phí của CẢ hồ sơ, store
    # vào đây thì mỗi lần sửa một dòng chi phí phải đi cập nhật ngược lại
    # bảng giá. Đổi lại, KHÔNG lọc/nhóm được theo field này trong search
    # view — Odoo chỉ cho domain trên cột có thật. Dòng lệch giá được tô
    # đỏ trong danh sách thay cho bộ lọc.
    price_conflict = fields.Boolean(
        string='Chi phí đang lệch giá', compute='_compute_usage',
        help='Cùng một item nhưng các dòng chi phí đang để giá khác nhau. '
             'Bấm áp dụng sẽ kéo tất cả về một giá — nên xem trước khi bấm, '
             'vì giá dự thầu sẽ đổi.')

    _uniq_res = models.Constraint(
        'unique(bid_id, resource_id)',
        'Item này đã có giá trong hồ sơ dự thầu.')

    # ==================================================================
    @api.depends('resource_id', 'price')
    def _compute_library(self):
        Price = self.env['rp.price.line']
        for rec in self:
            lib = Price.search(
                [('resource_id', '=', rec.resource_id.id)],
                order='id desc', limit=1)
            rec.library_price = lib.price if lib else 0.0
            rec.variance = (rec.price or 0.0) - rec.library_price
            rec.variance_pct = (
                rec.variance / rec.library_price * 100.0
                if rec.library_price else 0.0)

    def _compute_usage(self):
        """Đếm mức độ dùng, và soi xem chi phí có đang lệch giá không.

        File dự toán nhập vào hay có chuyện cùng một cần cẩu 25 tấn mà
        hai đầu việc để hai giá. Áp bảng giá xuống sẽ kéo tất cả về một
        mức — đúng ý đồ, nhưng con số dự thầu sẽ nhảy. Phải nói trước
        chứ không để người dùng bấm xong mới thấy tổng đổi.
        """
        RL = self.env['rp.bid.resource.line']
        for rec in self:
            lines = RL.search([
                ('bid_id', '=', rec.bid_id.id),
                ('resource_id', '=', rec.resource_id.id),
                ('is_percent', '=', False)])
            rec.line_count = len(lines)
            prices = sorted({
                round(l.unit_price, 2) for l in lines if l.unit_price})
            rec.hp_levels = len(prices)
            rec.hp_min = prices[0] if prices else 0.0
            rec.hp_max = prices[-1] if prices else 0.0
            rec.price_conflict = len(prices) > 1

    def action_apply(self):
        """Đẩy giá xuống mọi dòng chi phí dùng item này trong hồ sơ."""
        RL = self.env['rp.bid.resource.line']
        n = 0
        for rec in self:
            lines = RL.search([('bid_id', '=', rec.bid_id.id),
                               ('resource_id', '=', rec.resource_id.id)])
            lines.write({'unit_price': rec.price})
            n += len(lines)
        return self.env['rp.bid']._notify(
            _('Đã cập nhật %s dòng chi phí.', n))

    def action_take_library_price(self):
        for rec in self:
            if rec.library_price:
                rec.price = rec.library_price
                rec.source = 'library'


class RpBidPriceOnBid(models.Model):
    _inherit = 'rp.bid'

    price_ids = fields.One2many(
        'rp.bid.price', 'bid_id', string='Bảng giá hồ sơ')
    price_count = fields.Integer(compute='_compute_price_count')

    @api.depends('price_ids')
    def _compute_price_count(self):
        for bid in self:
            bid.price_count = len(bid.price_ids)

    def action_build_price_list(self):
        """Dựng bảng giá từ các item đang dùng trong chi phí.

        Lấy giá đang dùng làm điểm xuất phát chứ không để trống: hồ sơ
        nhập từ file dự toán vốn đã có giá, dựng ra bảng trống rồi bắt
        gõ lại 100 dòng là không ai làm.

        KHI MỘT ITEM ĐANG CÓ NHIỀU GIÁ trong chi phí thì lấy mức nào?
        Không lấy dòng gặp đầu tiên — đó là chọn theo thứ tự id, tức là
        ngẫu nhiên. Lấy mức **chiếm nhiều tiền nhất**: nó đại diện cho
        phần lớn khối lượng, nên kéo cả hồ sơ về mức đó ít làm xê dịch
        tổng nhất. Chỗ lệch được ghi vào ghi chú để còn kiểm lại.
        """
        Price = self.env['rp.bid.price']
        RL = self.env['rp.bid.resource.line']
        created = conflicts = 0
        for bid in self:
            have = set(bid.price_ids.mapped('resource_id').ids)
            weight = {}
            for rl in RL.search([('bid_id', '=', bid.id),
                                 ('is_percent', '=', False)]):
                rid = rl.resource_id.id
                if rid in have or not rl.unit_price:
                    continue
                w = weight.setdefault(rid, {})
                key = round(rl.unit_price, 2)
                w[key] = w.get(key, 0.0) + abs(rl.amount or 0.0)
            vals = []
            for rid, w in weight.items():
                best = max(w.items(), key=lambda kv: kv[1])[0]
                note = False
                if len(w) > 1:
                    conflicts += 1
                    note = _(
                        'Chi phí đang có %(n)s mức giá (%(lo)s … %(hi)s). '
                        'Lấy mức chiếm nhiều tiền nhất.',
                        n=len(w), lo='{:,.0f}'.format(min(w)),
                        hi='{:,.0f}'.format(max(w)))
                vals.append({'bid_id': bid.id, 'resource_id': rid,
                             'price': best, 'source': 'imported',
                             'note': note})
            if vals:
                Price.create(vals)
                created += len(vals)
        msg = _('Đã dựng %s dòng giá cho hồ sơ.', created)
        if conflicts:
            msg += _(
                ' Trong đó %s item đang để nhiều mức giá khác nhau trong hao '
                'phí — lọc cột "Chi phí đang lệch giá" để xem trước khi áp.',
                conflicts)
        return self._notify(msg)

    def action_apply_price_list(self):
        """Áp toàn bộ bảng giá xuống chi phí, rồi tính lại giá dự thầu."""
        n = 0
        before = sum(self.mapped('direct_cost'))
        for bid in self:
            for p in bid.price_ids:
                lines = self.env['rp.bid.resource.line'].search([
                    ('bid_id', '=', bid.id),
                    ('resource_id', '=', p.resource_id.id)])
                lines.write({'unit_price': p.price})
                n += len(lines)
        after = sum(self.mapped('direct_cost'))
        delta = after - before
        msg = _('Đã áp giá xuống %s dòng chi phí.', n)
        if abs(delta) >= 1:
            msg += _(' Chi phí trực tiếp đổi %(d)s đ, còn %(a)s đ.',
                     d='{:+,.0f}'.format(delta), a='{:,.0f}'.format(after))
        else:
            msg += _(' Chi phí trực tiếp không đổi.')
        return self._notify(msg)

    def action_open_prices(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Bảng giá — %s', self.name),
            'res_model': 'rp.bid.price',
            'view_mode': 'list,form',
            'domain': [('bid_id', '=', self.id)],
            'context': {'default_bid_id': self.id},
        }
