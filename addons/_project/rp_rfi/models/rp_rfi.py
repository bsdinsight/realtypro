# -*- coding: utf-8 -*-
"""rp.rfi — Phiếu yêu cầu làm rõ (Request for Information).

Nhà thầu/kỹ sư hỏi TVGS/Thiết kế/CĐT khi vướng bản vẽ, xung đột thiết
kế, thiếu thông tin. Đồng hồ đếm ngày chờ trả lời là con số CĐT nhìn
mỗi sáng — RFI trễ là căn cứ claim tiến độ của nhà thầu.
"""
from odoo import _, api, fields, models

RECIPIENT = [
    ('supervisor', 'Tư vấn giám sát (TVGS)'),
    ('designer', 'Tư vấn thiết kế'),
    ('owner', 'Chủ đầu tư / BQLDA'),
    ('gc', 'Tổng thầu'),
]


class RpRfi(models.Model):
    _name = 'rp.rfi'
    _description = 'RFI — Phiếu yêu cầu làm rõ'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'state, deadline, id desc'

    code = fields.Char(
        string='Số RFI', required=True, copy=False, readonly=True,
        default=lambda self: _('Mới'))
    name = fields.Char(string='Câu hỏi (tóm tắt)', required=True,
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
    location = fields.Char(
        string='Vị trí / bản vẽ liên quan',
        help='Vd: "Trục 5-6 tầng hầm — bản vẽ KC-05 rev.2".')
    recipient = fields.Selection(
        RECIPIENT, string='Gửi tới', required=True,
        default='supervisor', tracking=True)
    question = fields.Text(string='Nội dung câu hỏi')
    requested_by_id = fields.Many2one(
        'res.users', string='Người hỏi', required=True,
        default=lambda self: self.env.user)
    submitted_date = fields.Date(string='Ngày gửi', copy=False)
    deadline = fields.Date(string='Hạn trả lời', tracking=True)
    impact_cost = fields.Boolean(
        string='Ảnh hưởng chi phí', tracking=True,
        help='Câu trả lời có thể làm thay đổi chi phí (phát sinh).')
    impact_schedule = fields.Boolean(
        string='Ảnh hưởng tiến độ', tracking=True,
        help='Công việc đang chờ câu trả lời — chậm trả lời là chậm '
             'tiến độ (căn cứ claim).')
    answer = fields.Text(string='Nội dung trả lời')
    answered_by_id = fields.Many2one(
        'res.users', string='Người trả lời', readonly=True, copy=False)
    answered_date = fields.Date(string='Ngày trả lời', readonly=True,
                                copy=False)
    days_waiting = fields.Integer(
        string='Số ngày chờ', compute='_compute_days_waiting',
        help='Từ ngày gửi đến ngày trả lời (hoặc hôm nay nếu chưa '
             'trả lời).')
    is_overdue = fields.Boolean(
        string='Quá hạn', compute='_compute_days_waiting')
    attachment_ids = fields.Many2many(
        'ir.attachment', string='Ảnh / tài liệu đính kèm')
    state = fields.Selection([
        ('draft', 'Nháp'),
        ('submitted', 'Đã gửi — chờ trả lời'),
        ('answered', 'Đã trả lời'),
        ('closed', 'Đóng'),
        ('cancelled', 'Huỷ'),
    ], default='draft', string='Trạng thái', tracking=True, copy=False)

    def _compute_days_waiting(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.submitted_date:
                end = rec.answered_date or today
                rec.days_waiting = (end - rec.submitted_date).days
            else:
                rec.days_waiting = 0
            rec.is_overdue = bool(
                rec.deadline and rec.deadline < today
                and rec.state == 'submitted')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('code', _('Mới')) == _('Mới'):
                vals['code'] = self.env['ir.sequence'].next_by_code(
                    'rp.rfi') or _('Mới')
        return super().create(vals_list)

    def action_submit(self):
        self.write({'state': 'submitted',
                    'submitted_date': fields.Date.context_today(self)})

    def action_answer(self):
        for rec in self:
            if not rec.answer:
                from odoo.exceptions import UserError
                raise UserError(_(
                    'Nhập nội dung trả lời trước khi xác nhận.'))
        self.write({'state': 'answered',
                    'answered_by_id': self.env.user.id,
                    'answered_date': fields.Date.context_today(self)})

    def action_close(self):
        self.write({'state': 'closed'})

    def action_reopen(self):
        self.write({'state': 'submitted', 'answered_by_id': False,
                    'answered_date': False})

    def action_cancel(self):
        self.write({'state': 'cancelled'})
