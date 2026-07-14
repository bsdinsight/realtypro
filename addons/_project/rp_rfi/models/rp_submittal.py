# -*- coding: utf-8 -*-
"""rp.submittal — Trình duyệt mẫu vật liệu / shopdrawing / biện pháp.

Nhà thầu trình → TVGS/CĐT/Thiết kế duyệt / duyệt có điều kiện / từ
chối. Từ chối thì trình lại (revision +1). Sổ trình duyệt là hồ sơ
chất lượng bắt buộc trước khi đưa vật liệu vào công trường — punch
"vật liệu sai chủng loại phê duyệt" chính là hậu quả khi thiếu sổ này.
"""
from odoo import _, api, fields, models

SUBMITTAL_TYPE = [
    ('material', 'Mẫu vật liệu'),
    ('shopdrawing', 'Bản vẽ chế tạo (shopdrawing)'),
    ('method', 'Biện pháp thi công'),
    ('mockup', 'Mock-up / phòng mẫu'),
    ('other', 'Khác'),
]


class RpSubmittal(models.Model):
    _name = 'rp.submittal'
    _description = 'Trình duyệt (Submittal)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'state, deadline, id desc'

    code = fields.Char(
        string='Số trình duyệt', required=True, copy=False, readonly=True,
        default=lambda self: _('Mới'))
    name = fields.Char(string='Hạng mục trình duyệt', required=True,
                       tracking=True)
    submittal_type = fields.Selection(
        SUBMITTAL_TYPE, string='Loại', required=True, default='material',
        tracking=True)
    project_id = fields.Many2one(
        're.project', string='Dự án', required=True, index=True)
    contract_id = fields.Many2one(
        'rp.contract', string='HĐ nhà thầu', index=True,
        domain="[('project_id', '=', project_id)]", tracking=True)
    contractor_id = fields.Many2one(
        related='contract_id.contractor_id', string='Nhà thầu',
        store=True, index=True)
    structure_id = fields.Many2one(
        'rp.structure', string='Hạng mục',
        domain="[('project_id', '=', project_id)]")
    description = fields.Text(
        string='Mô tả',
        help='Thông số, xuất xứ, tiêu chuẩn áp dụng, phạm vi sử dụng…')
    submitted_by_id = fields.Many2one(
        'res.users', string='Người trình', required=True,
        default=lambda self: self.env.user)
    submitted_date = fields.Date(string='Ngày trình', copy=False)
    deadline = fields.Date(string='Hạn duyệt', tracking=True)
    revision = fields.Integer(
        string='Lần trình', default=1, readonly=True, copy=False,
        help='Tăng mỗi lần trình lại sau khi bị từ chối.')
    reviewed_by_id = fields.Many2one(
        'res.users', string='Người duyệt', readonly=True, copy=False)
    reviewed_date = fields.Date(string='Ngày duyệt', readonly=True,
                                copy=False)
    review_note = fields.Text(
        string='Ý kiến duyệt',
        help='Điều kiện kèm theo (nếu duyệt có điều kiện) hoặc lý do '
             'từ chối.')
    is_overdue = fields.Boolean(
        string='Quá hạn duyệt', compute='_compute_is_overdue')
    attachment_ids = fields.Many2many(
        'ir.attachment', string='Ảnh mẫu / bản vẽ / catalogue')
    state = fields.Selection([
        ('draft', 'Nháp'),
        ('submitted', 'Đã trình — chờ duyệt'),
        ('approved', 'Đã duyệt'),
        ('approved_cond', 'Duyệt có điều kiện'),
        ('rejected', 'Từ chối — trình lại'),
        ('cancelled', 'Huỷ'),
    ], default='draft', string='Trạng thái', tracking=True, copy=False)

    def _compute_is_overdue(self):
        today = fields.Date.context_today(self)
        for rec in self:
            rec.is_overdue = bool(
                rec.deadline and rec.deadline < today
                and rec.state == 'submitted')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('code', _('Mới')) == _('Mới'):
                vals['code'] = self.env['ir.sequence'].next_by_code(
                    'rp.submittal') or _('Mới')
        return super().create(vals_list)

    def action_submit(self):
        self.write({'state': 'submitted',
                    'submitted_date': fields.Date.context_today(self)})

    def _review(self, state):
        self.write({'state': state,
                    'reviewed_by_id': self.env.user.id,
                    'reviewed_date': fields.Date.context_today(self)})

    def action_approve(self):
        self._review('approved')

    def action_approve_cond(self):
        self._review('approved_cond')

    def action_reject(self):
        self._review('rejected')

    def action_resubmit(self):
        self.write({'state': 'submitted',
                    'revision': self.revision + 1,
                    'submitted_date': fields.Date.context_today(self),
                    'reviewed_by_id': False, 'reviewed_date': False})

    def action_cancel(self):
        self.write({'state': 'cancelled'})
