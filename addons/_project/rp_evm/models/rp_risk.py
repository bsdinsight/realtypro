# -*- coding: utf-8 -*-
"""Đăng ký rủi ro dự án (Risk Register) — bộ ba quản trị PM
Issues · Changes · **Risks**.

Ma trận 5×5: Khả năng (probability) × Mức ảnh hưởng (impact) → điểm rủi ro
(score = P×I, 1..25) → mức (Thấp/Trung bình/Cao/Nghiêm trọng). Nuôi
bản đồ nhiệt rủi ro + bảng rủi ro trọng yếu trên Bảng điều khiển EVM.
"""
from odoo import _, api, fields, models

PROBABILITY = [
    ('1', '1 · Hiếm khi'),
    ('2', '2 · Ít khả năng'),
    ('3', '3 · Có thể'),
    ('4', '4 · Nhiều khả năng'),
    ('5', '5 · Gần như chắc chắn'),
]
IMPACT = [
    ('1', '1 · Không đáng kể'),
    ('2', '2 · Nhẹ'),
    ('3', '3 · Trung bình'),
    ('4', '4 · Nặng'),
    ('5', '5 · Nghiêm trọng'),
]


class RpRisk(models.Model):
    _name = 'rp.risk'
    _description = 'Đăng ký rủi ro dự án'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'score desc, id desc'

    code = fields.Char(
        string='Mã', required=True, copy=False, readonly=True,
        default=lambda self: _('Mới'))
    name = fields.Char(string='Rủi ro', required=True, tracking=True)
    project_id = fields.Many2one(
        're.project', string='Dự án', required=True, index=True,
        default=lambda self: self.env['re.project'].search([], limit=1))
    contract_id = fields.Many2one(
        'rp.contract', string='Gói thầu liên quan',
        domain="[('project_id', '=', project_id)]")
    category = fields.Selection([
        ('schedule', 'Tiến độ'),
        ('cost', 'Chi phí'),
        ('quality', 'Chất lượng'),
        ('safety', 'An toàn'),
        ('procurement', 'Cung ứng / Vật tư'),
        ('design', 'Thiết kế'),
        ('external', 'Bên ngoài (thời tiết/pháp lý)'),
        ('financial', 'Tài chính / Dòng tiền'),
        ('other', 'Khác'),
    ], string='Nhóm', default='schedule', required=True, tracking=True)

    probability = fields.Selection(
        PROBABILITY, string='Khả năng', default='3', required=True,
        tracking=True)
    impact = fields.Selection(
        IMPACT, string='Mức ảnh hưởng', default='3', required=True,
        tracking=True)
    score = fields.Integer(
        string='Điểm rủi ro', compute='_compute_score', store=True,
        help='Khả năng × Mức ảnh hưởng (1..25).')
    level = fields.Selection([
        ('low', 'Thấp'),
        ('medium', 'Trung bình'),
        ('high', 'Cao'),
        ('critical', 'Nghiêm trọng'),
    ], string='Mức', compute='_compute_score', store=True, tracking=True)

    state = fields.Selection([
        ('open', 'Đang mở'),
        ('mitigating', 'Đang giảm thiểu'),
        ('closed', 'Đã đóng'),
        ('realized', 'Đã xảy ra'),
    ], string='Trạng thái', default='open', required=True, tracking=True)
    owner_id = fields.Many2one(
        'res.users', string='Người phụ trách',
        default=lambda self: self.env.user)
    date_identified = fields.Date(
        string='Ngày nhận diện', default=fields.Date.context_today)
    due_date = fields.Date(string='Hạn xử lý')
    impact_note = fields.Char(
        string='Ảnh hưởng cụ thể',
        help='Mô tả ngắn hệ quả nếu rủi ro xảy ra (VD: chậm 2 tuần).')
    mitigation = fields.Text(string='Biện pháp giảm thiểu')

    currency_id = fields.Many2one(
        related='project_id.currency_id', readonly=True)
    cost_exposure = fields.Monetary(
        string='Giá trị rủi ro (ước tính)', currency_field='currency_id')

    @api.depends('probability', 'impact')
    def _compute_score(self):
        for r in self:
            p = int(r.probability or 0)
            i = int(r.impact or 0)
            s = p * i
            r.score = s
            r.level = (
                'critical' if s >= 15 else
                'high' if s >= 10 else
                'medium' if s >= 5 else 'low')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('code', _('Mới')) == _('Mới'):
                vals['code'] = self.env['ir.sequence'].next_by_code(
                    'rp.risk') or _('Mới')
        return super().create(vals_list)

    def action_mitigate(self):
        self.write({'state': 'mitigating'})

    def action_close(self):
        self.write({'state': 'closed'})
