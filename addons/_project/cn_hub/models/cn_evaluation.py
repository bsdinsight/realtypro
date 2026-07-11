# -*- coding: utf-8 -*-
"""Chấm thầu — đánh giá HSDT & chọn nhà thầu (Luật ĐT 22/2023, NĐ 214/2025).

Quy trình tuần tự loại trực tiếp: hợp lệ → năng lực → kỹ thuật → tài chính
(sửa lỗi/hiệu chỉnh → giá đánh giá) → xếp hạng → đề nghị trúng thầu.

Số hiệu Điều để ở comment cấu hình, KHÔNG hardcode (văn bản hay đổi). Các
con số chốt cứng đã xác nhận nhiều nguồn: K 10-30% / G 70-90% (xây lắp),
ngưỡng KT ≥70%, sai lệch thiếu ≤10%.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

EVAL_METHOD = [
    ('lowest_price', 'Giá thấp nhất'),
    ('evaluated_price', 'Giá đánh giá'),
    ('tech_combined', 'Kết hợp kỹ thuật và giá'),
    ('tech_based', 'Dựa trên kỹ thuật'),
]

# Bộ tiêu chí kỹ thuật mặc định (trọng số minh hoạ — chủ đầu tư chỉnh được)
TECH_TEMPLATES = {
    'civil': [
        ('Giải pháp kỹ thuật & biện pháp tổ chức thi công', 30, 60),
        ('Tiến độ thi công (hợp lý, khả thi)', 15, 50),
        ('Tổ chức quản lý dự án / hiện trường & bảo đảm chất lượng', 20, 50),
        ('Nhân sự chủ chốt huy động', 15, 50),
        ('Thiết bị thi công chủ yếu', 10, 50),
        ('An toàn lao động, VSMT, PCCC', 5, 50),
        ('Uy tín / kết quả thực hiện HĐ tương tự', 5, 0),
    ],
    'hospital': [
        ('Giải pháp kỹ thuật & biện pháp tổ chức thi công', 22, 60),
        ('Hệ cơ điện MEP (điện nhẹ, HVAC, khí y tế, xử lý nước thải y tế)', 18, 60),
        ('Phòng sạch / kiểm soát nhiễm khuẩn (mổ, ICU)', 12, 60),
        ('Thi công trong môi trường bệnh viện đang vận hành', 8, 50),
        ('Tiến độ thi công', 12, 50),
        ('Tổ chức QLDA & bảo đảm chất lượng', 12, 50),
        ('Nhân sự chủ chốt & thiết bị', 8, 50),
        ('PCCC & an toàn cho công trình đông người', 8, 60),
    ],
}


class CnTenderEval(models.Model):
    _inherit = 'cn.tender'

    eval_method = fields.Selection(
        EVAL_METHOD, string='Phương pháp đánh giá', default='lowest_price',
        help='Xây lắp phổ biến: Giá thấp nhất / Giá đánh giá (KT Đạt-KĐ). '
             'Kết hợp KT-giá khi cần phân biệt chất lượng kỹ thuật.')
    tech_weight = fields.Float(
        string='Trọng số kỹ thuật K (%)', default=20,
        help='Chỉ dùng khi Kết hợp KT-giá. Xây lắp: K = 10–30%.')
    price_weight = fields.Float(
        string='Trọng số giá G (%)', default=80,
        help='Xây lắp: G = 70–90%. K + G = 100.')
    tech_threshold = fields.Float(
        string='Ngưỡng điểm KT đạt (%)', default=70,
        help='Điểm kỹ thuật tối thiểu để qua vòng KT (thường ≥70%, gói '
             'yêu cầu cao 80–90%).')
    tech_criterion_ids = fields.One2many(
        'cn.tender.tech.criterion', 'tender_id', string='Tiêu chí kỹ thuật')
    criteria_template = fields.Selection(
        [('civil', 'Xây lắp dân dụng'), ('hospital', 'Bệnh viện / Y tế')],
        string='Mẫu tiêu chí', default='civil')

    @api.constrains('eval_method', 'tech_weight', 'price_weight')
    def _check_weights(self):
        for t in self:
            if t.eval_method != 'tech_combined':
                continue
            if abs((t.tech_weight + t.price_weight) - 100) > 0.01:
                raise ValidationError(_('K + G phải bằng 100%.'))
            if not (10 <= t.tech_weight <= 30):
                raise ValidationError(_(
                    'Gói xây lắp: trọng số kỹ thuật K phải trong 10–30%%.'))

    def action_load_tech_criteria(self):
        Crit = self.env['cn.tender.tech.criterion']
        for t in self:
            if t.tech_criterion_ids:
                continue
            seq = 10
            for name, weight, minp in TECH_TEMPLATES.get(
                    t.criteria_template, TECH_TEMPLATES['civil']):
                Crit.create({'tender_id': t.id, 'name': name,
                             'weight': weight, 'min_pct': minp,
                             'sequence': seq})
                seq += 10
        return True

    # ------------------------------------------------------------------
    # Chấm thầu: chạy pipeline cho mọi HSDT đã nộp → xếp hạng
    # ------------------------------------------------------------------
    def action_evaluate(self):
        self.ensure_one()
        bids = self.bid_ids.filtered(lambda b: b.is_submitted)
        if not bids:
            raise UserError(_('Chưa có hồ sơ dự thầu nào được nộp chính thức.'))
        # 1) đảm bảo mỗi HSDT có đủ dòng chấm điểm theo tiêu chí
        for b in bids:
            b._sync_tech_scores()
        # 2) lọc qua các cửa: hợp lệ → năng lực → kỹ thuật → giá (±10%)
        qualified = bids.filtered(lambda b: (
            b.eligible and b.capacity_passed and b.tech_passed
            and not b.price_over_limit))
        # 3) xếp hạng theo phương pháp
        for b in bids:
            b.rank = 0
            b.price_score = 0.0
            b.total_score = 0.0
        if self.eval_method == 'tech_combined':
            gmin = min(qualified.mapped('evaluated_price') or [0]) or 0
            for b in qualified:
                b.price_score = (100.0 * gmin / b.evaluated_price
                                 if b.evaluated_price else 0.0)
                b.total_score = (self.tech_weight / 100.0 * b.tech_score_pct
                                 + self.price_weight / 100.0 * b.price_score)
            ordered = qualified.sorted(key=lambda b: -b.total_score)
        elif self.eval_method == 'tech_based':
            ordered = qualified.sorted(key=lambda b: -b.tech_score_pct)
        else:  # lowest_price / evaluated_price → giá đánh giá tăng dần
            ordered = qualified.sorted(key=lambda b: b.evaluated_price)
        for i, b in enumerate(ordered, start=1):
            b.rank = i
        # cập nhật eval_state
        for b in bids:
            if b not in qualified:
                b.eval_state = 'failed'
            elif b.rank == 1:
                b.eval_state = 'ranked1'
            else:
                b.eval_state = 'ranked'
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {
                'title': _('Chấm thầu'),
                'message': _('Đã đánh giá %(n)s hồ sơ, %(q)s đạt, xếp hạng xong.',
                             n=len(bids), q=len(qualified)),
                'type': 'success', 'sticky': False}}


class CnTenderTechCriterion(models.Model):
    _name = 'cn.tender.tech.criterion'
    _description = 'Tiêu chí đánh giá kỹ thuật'
    _order = 'tender_id, sequence, id'

    tender_id = fields.Many2one(
        'cn.tender', string='Gói thầu', required=True, ondelete='cascade',
        index=True)
    sequence = fields.Integer(default=10)
    name = fields.Char(string='Tiêu chí', required=True)
    weight = fields.Float(string='Trọng số (%)', default=10)
    min_pct = fields.Float(
        string='% tối thiểu', default=50,
        help='Mức đáp ứng tối thiểu của riêng tiêu chí này (điểm/100). '
             'Dưới mức → trượt kỹ thuật.')


class CnBidEval(models.Model):
    _inherit = 'cn.bid'

    eval_state = fields.Selection(
        [('pending', 'Chờ đánh giá'),
         ('failed', 'Bị loại'),
         ('ranked', 'Đã xếp hạng'),
         ('ranked1', 'Xếp hạng 1')],
        string='Trạng thái chấm', default='pending', tracking=True)
    # Cửa Đạt/Không đạt (người chấm đặt)
    eligible = fields.Boolean(string='Hợp lệ (HSDT)')
    capacity_passed = fields.Boolean(string='Đạt năng lực & kinh nghiệm')
    # Kỹ thuật
    tech_score_ids = fields.One2many(
        'cn.bid.tech.score', 'bid_id', string='Chấm điểm kỹ thuật')
    tech_score_pct = fields.Float(
        string='Điểm KT (%)', compute='_compute_tech', store=True)
    tech_passed = fields.Boolean(
        string='Đạt kỹ thuật', compute='_compute_tech', store=True)
    # Tài chính — sửa lỗi / hiệu chỉnh sai lệch → giá đánh giá
    price_corrected = fields.Monetary(
        string='Giá sau sửa lỗi', currency_field='currency_id',
        help='Giá dự thầu sau sửa lỗi số học & trừ giảm giá. Mặc định = giá dự thầu.')
    deviation_missing = fields.Monetary(
        string='Sai lệch thiếu', currency_field='currency_id',
        help='Giá trị phần thiếu so với HSMT (cộng vào giá đánh giá).')
    deviation_surplus = fields.Monetary(
        string='Sai lệch thừa', currency_field='currency_id')
    evaluated_price = fields.Monetary(
        string='Giá đánh giá', compute='_compute_eval_price', store=True,
        currency_field='currency_id')
    price_over_limit = fields.Boolean(
        string='Vượt ±10% (loại)', compute='_compute_eval_price', store=True,
        help='Sai lệch thiếu > 10% giá dự thầu → loại HSDT.')
    # Kết quả (do action_evaluate ghi)
    price_score = fields.Float(string='Điểm giá', readonly=True)
    total_score = fields.Float(string='Điểm tổng hợp', readonly=True)
    rank = fields.Integer(string='Xếp hạng', readonly=True)

    @api.depends('tech_score_ids.score', 'tech_score_ids.criterion_id.weight',
                 'tech_score_ids.criterion_id.min_pct',
                 'tender_id.tech_threshold')
    def _compute_tech(self):
        for b in self:
            lines = b.tech_score_ids
            tw = sum(l.criterion_id.weight for l in lines)
            b.tech_score_pct = (
                sum(l.score * l.criterion_id.weight for l in lines) / tw
                if tw else 0.0)
            crit_ok = all(l.score >= l.criterion_id.min_pct for l in lines) \
                if lines else False
            b.tech_passed = bool(lines) and crit_ok \
                and b.tech_score_pct >= (b.tender_id.tech_threshold or 70)

    @api.depends('price_corrected', 'price', 'deviation_missing',
                 'deviation_surplus')
    def _compute_eval_price(self):
        for b in self:
            base = b.price_corrected or b.price
            b.evaluated_price = base + b.deviation_missing - b.deviation_surplus
            b.price_over_limit = bool(base) and b.deviation_missing > 0.10 * base

    def _sync_tech_scores(self):
        """Tạo dòng chấm điểm cho mỗi tiêu chí của gói (nếu thiếu)."""
        Score = self.env['cn.bid.tech.score']
        for b in self:
            have = b.tech_score_ids.mapped('criterion_id').ids
            for c in b.tender_id.tech_criterion_ids:
                if c.id not in have:
                    Score.create({'bid_id': b.id, 'criterion_id': c.id})
        return True

    def action_prepare_scores(self):
        self._sync_tech_scores()
        return True


class CnBidTechScore(models.Model):
    _name = 'cn.bid.tech.score'
    _description = 'Điểm kỹ thuật theo tiêu chí'
    _order = 'bid_id, criterion_id'

    bid_id = fields.Many2one(
        'cn.bid', string='Hồ sơ dự thầu', required=True, ondelete='cascade',
        index=True)
    criterion_id = fields.Many2one(
        'cn.tender.tech.criterion', string='Tiêu chí', required=True,
        ondelete='cascade')
    weight = fields.Float(related='criterion_id.weight', string='Trọng số (%)')
    min_pct = fields.Float(related='criterion_id.min_pct')
    score = fields.Float(string='Điểm (/100)')
    note = fields.Char(string='Nhận xét')

    _uniq = models.Constraint(
        'unique(bid_id, criterion_id)',
        'Mỗi tiêu chí chỉ chấm 1 lần / hồ sơ.')
