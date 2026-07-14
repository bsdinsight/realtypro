# -*- coding: utf-8 -*-
"""rp.site.punch — Punch list: lỗi/khiếm khuyết phát hiện tại hiện
trường và vòng đời khắc phục.

Mở → Đang xử lý → Đã khắc phục (nhà thầu báo xong) → Đóng (nghiệm thu
lại đạt). Punch còn mở trên HĐ là tín hiệu chặn/cảnh báo khi nghiệm
thu — thanh toán (smart button trên HĐ nhà thầu).
"""
from odoo import _, api, fields, models


class RpSitePunch(models.Model):
    _name = 'rp.site.punch'
    _description = 'Punch list — lỗi & khắc phục'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'state, deadline, id desc'

    code = fields.Char(
        string='Mã', required=True, copy=False, readonly=True,
        default=lambda self: _('Mới'))
    name = fields.Char(string='Lỗi / khiếm khuyết', required=True,
                       tracking=True)
    project_id = fields.Many2one(
        're.project', string='Dự án', required=True, index=True)
    structure_id = fields.Many2one(
        'rp.structure', string='Hạng mục',
        domain="[('project_id', '=', project_id)]")
    contract_id = fields.Many2one(
        'rp.contract', string='HĐ nhà thầu', index=True,
        domain="[('project_id', '=', project_id)]", tracking=True)
    responsible_id = fields.Many2one(
        'res.partner', string='Nhà thầu chịu trách nhiệm',
        domain=[('is_company', '=', True)], tracking=True)
    location = fields.Char(
        string='Vị trí', help='Vd: "Tầng 3, trục B-C, phòng mổ số 2".')
    description = fields.Text(string='Mô tả chi tiết')
    severity = fields.Selection([
        ('minor', 'Nhẹ'),
        ('major', 'Nặng'),
        ('critical', 'Nghiêm trọng'),
    ], default='minor', string='Mức độ', required=True, tracking=True)
    deadline = fields.Date(string='Hạn khắc phục', tracking=True)
    is_overdue = fields.Boolean(
        string='Quá hạn', compute='_compute_is_overdue')
    diary_id = fields.Many2one(
        'rp.site.diary', string='Phát hiện từ nhật ký', ondelete='set null')
    assigned_user_id = fields.Many2one(
        'res.users', string='Người theo dõi',
        default=lambda self: self.env.user)
    attachment_ids = fields.Many2many(
        'ir.attachment', string='Ảnh lỗi / ảnh khắc phục')
    fixed_date = fields.Date(string='Ngày khắc phục xong', copy=False)
    closed_date = fields.Date(string='Ngày đóng', copy=False)
    state = fields.Selection([
        ('open', 'Mở'),
        ('in_progress', 'Đang xử lý'),
        ('fixed', 'Đã khắc phục'),
        ('closed', 'Đóng (đã nghiệm thu lại)'),
        ('cancelled', 'Huỷ'),
    ], default='open', string='Trạng thái', tracking=True, copy=False)

    def _compute_is_overdue(self):
        today = fields.Date.context_today(self)
        for rec in self:
            rec.is_overdue = bool(
                rec.deadline and rec.deadline < today
                and rec.state in ('open', 'in_progress'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('code', _('Mới')) == _('Mới'):
                vals['code'] = self.env['ir.sequence'].next_by_code(
                    'rp.site.punch') or _('Mới')
        return super().create(vals_list)

    def action_start(self):
        self.write({'state': 'in_progress'})

    def action_fixed(self):
        self.write({'state': 'fixed',
                    'fixed_date': fields.Date.context_today(self)})

    def action_close(self):
        self.write({'state': 'closed',
                    'closed_date': fields.Date.context_today(self)})

    def action_reopen(self):
        self.write({'state': 'open', 'fixed_date': False,
                    'closed_date': False})

    def action_cancel(self):
        self.write({'state': 'cancelled'})
