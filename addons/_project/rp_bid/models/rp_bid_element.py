# -*- coding: utf-8 -*-
"""rp.bid.element — Cấu kiện được bóc tách (cọc, panel tường vây…).

VÌ SAO LÀ MỘT DANH MỤC RIÊNG, KHÔNG PHẢI MÃ TỰ TĂNG TRÊN TỪNG DÒNG:

Trong bộ dữ liệu thật có 302 dòng bóc tách nhưng chỉ **38 nhãn**. Nhãn
`CTN2 D1200` xuất hiện **22 lần** — ở khoan tạo lỗ, đào xúc đất, bơm
polymer, đổ bê tông, cốt thép, ống siêu âm. Sự lặp lại đó là CÓ CHỦ Ý:
đọc dọc theo một nhãn là thấy một cây cọc ngốn hết những gì.

Đánh mã tự tăng theo từng DÒNG sẽ ra `CK-01…CK-302` và mất sạch tính
chất ấy. Đánh mã cho CẤU KIỆN thì vừa tự tăng được, vừa giữ được việc
nhiều dòng cùng trỏ về một cọc.

ĐÂY CŨNG LÀ CHỖ MÓC SANG THEO DÕI THI CÔNG. Khi cần quản tới từng cọc
(ngày khoan, cao trình thực tế, kết quả siêu âm, toạ độ tim cọc), thêm
trường vào đây là đủ — không phải đập đi làm lại phần bóc tách.

Cấu kiện thuộc về MỘT hồ sơ dự thầu: mỗi gói thầu có bộ cọc riêng, và
cách đánh số của gói này không liên quan gói khác.
"""
from odoo import _, api, fields, models


class RpBidElement(models.Model):
    _name = 'rp.bid.element'
    _description = 'Cấu kiện bóc tách (cọc, panel…)'
    _order = 'bid_id, code'

    bid_id = fields.Many2one(
        'rp.bid', string='Hồ sơ dự thầu', required=True,
        ondelete='cascade', index=True)
    project_id = fields.Many2one(
        related='bid_id.project_id', string='Dự án', store=True, index=True)
    package_id = fields.Many2one(
        related='bid_id.package_id', string='Gói thầu', store=True, index=True)

    code = fields.Char(
        string='Mã cấu kiện', required=True, index=True, copy=False,
        help='Tự sinh theo tiền tố khai ở hồ sơ dự thầu. Sửa tay được nếu '
             'muốn giữ đúng ký hiệu trong bản vẽ.')
    name = fields.Char(
        string='Tên / diễn giải', required=True, translate=True,
        help='VD "Cọc thí nghiệm số 2, D1200", "Panel tường vây T5A".')

    takeoff_ids = fields.One2many(
        'rp.bid.takeoff', 'element_id', string='Dòng bóc tách')
    takeoff_count = fields.Integer(compute='_compute_usage', store=True)
    line_count = fields.Integer(
        string='Số đầu việc', compute='_compute_usage', store=True,
        help='Số dòng BoQ có nhắc tới cấu kiện này — cho biết một cấu kiện '
             'đi qua bao nhiêu công việc.')

    note = fields.Text(string='Ghi chú')
    active = fields.Boolean(default=True)

    _uniq_code = models.Constraint(
        'unique(bid_id, code)',
        'Mã cấu kiện đã có trong hồ sơ dự thầu này.')

    @api.depends('takeoff_ids', 'takeoff_ids.line_id')
    def _compute_usage(self):
        for rec in self:
            rec.takeoff_count = len(rec.takeoff_ids)
            rec.line_count = len(rec.takeoff_ids.mapped('line_id'))

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '[%s] %s' % (rec.code or '', rec.name or '')

    # ==================================================================
    @api.model_create_multi
    def create(self, vals_list):
        """Sinh mã theo tiền tố của hồ sơ nếu người dùng không tự đặt.

        Lấy số lớn nhất đang có trong CÙNG hồ sơ rồi cộng một, thay vì
        đếm số bản ghi: xoá một cấu kiện giữa chừng rồi tạo mới sẽ trùng
        mã nếu đếm.
        """
        by_bid = {}
        for vals in vals_list:
            if vals.get('code') or not vals.get('bid_id'):
                continue
            bid = self.env['rp.bid'].browse(vals['bid_id'])
            prefix = (bid.element_prefix or 'CK').strip()
            if bid.id not in by_bid:
                by_bid[bid.id] = self._next_number(bid.id, prefix)
            by_bid[bid.id] += 1
            vals['code'] = '%s-%02d' % (prefix, by_bid[bid.id])
        return super().create(vals_list)

    @api.model
    def _next_number(self, bid_id, prefix):
        existing = self.with_context(active_test=False).search(
            [('bid_id', '=', bid_id), ('code', '=like', prefix + '-%')])
        biggest = 0
        for rec in existing:
            tail = (rec.code or '').rsplit('-', 1)[-1]
            if tail.isdigit():
                biggest = max(biggest, int(tail))
        return biggest

    def action_open_takeoffs(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Bóc tách của %s', self.display_name),
            'res_model': 'rp.bid.takeoff',
            'view_mode': 'list,form',
            'domain': [('element_id', '=', self.id)],
            'context': {'default_element_id': self.id},
        }


class RpBidElementOnBid(models.Model):
    _inherit = 'rp.bid'

    element_prefix = fields.Char(
        string='Tiền tố mã cấu kiện', default='CK',
        help='Mã cấu kiện tự sinh theo tiền tố này: CK-01, CK-02… Đổi '
             'thành CTN, CĐT, T… nếu muốn bám ký hiệu trong bản vẽ.')
    element_ids = fields.One2many(
        'rp.bid.element', 'bid_id', string='Cấu kiện')
    element_count = fields.Integer(compute='_compute_element_count')

    @api.depends('element_ids')
    def _compute_element_count(self):
        for bid in self:
            bid.element_count = len(bid.element_ids)

    def action_open_elements(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Cấu kiện — %s', self.name),
            'res_model': 'rp.bid.element',
            'view_mode': 'list,form',
            'domain': [('bid_id', '=', self.id)],
            'context': {'default_bid_id': self.id},
        }


class RpBidTakeoffElement(models.Model):
    _inherit = 'rp.bid.takeoff'

    element_id = fields.Many2one(
        'rp.bid.element', string='Cấu kiện',
        ondelete='restrict', index=True,
        domain="[('bid_id', '=', bid_id)]",
        help='Cọc / panel / cấu kiện mà dòng bóc tách này đo. Để trống với '
             'dòng không gắn vào cấu kiện cụ thể — dòng trừ chung, dòng '
             'lấy số từ bảng thống kê thép…')
    bid_id = fields.Many2one(
        related='line_id.bid_id', string='Hồ sơ dự thầu', store=True,
        index=True)

    @api.onchange('element_id')
    def _onchange_element_fills_name(self):
        """Chọn cấu kiện thì điền sẵn diễn giải — khỏi gõ hai lần."""
        if self.element_id and not self.name:
            self.name = self.element_id.name
