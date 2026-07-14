# -*- coding: utf-8 -*-
"""rp.site.instruction — Chỉ thị công trường (Site Instruction).

Chiều ngược của RFI: CĐT/TVGS ra chỉ thị chính thức cho nhà thầu —
yêu cầu thực hiện/sửa đổi, có hạn, có cờ phát sinh chi phí (về sau
là căn cứ phụ lục HĐ). Nhà thầu xác nhận thực hiện kèm ảnh; bên ra
chỉ thị nghiệm thu và đóng.
"""
from odoo import _, api, fields, models


class RpSiteInstruction(models.Model):
    _name = 'rp.site.instruction'
    _description = 'Chỉ thị công trường (Site Instruction)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'state, deadline, id desc'

    code = fields.Char(
        string='Số chỉ thị', required=True, copy=False, readonly=True,
        default=lambda self: _('Mới'))
    name = fields.Char(string='Nội dung chỉ thị (tóm tắt)',
                       required=True, tracking=True)
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
    location = fields.Char(string='Vị trí')
    issued_by_id = fields.Many2one(
        'res.users', string='Người ra chỉ thị', required=True,
        default=lambda self: self.env.user)
    issued_date = fields.Date(string='Ngày phát hành', copy=False)
    deadline = fields.Date(string='Hạn thực hiện', tracking=True)
    description = fields.Text(string='Nội dung chi tiết')
    cost_impact = fields.Boolean(
        string='Phát sinh chi phí', tracking=True,
        help='Chỉ thị làm phát sinh chi phí — căn cứ lập phụ lục HĐ.')
    done_date = fields.Date(string='Ngày hoàn thành', readonly=True,
                            copy=False)
    done_note = fields.Text(
        string='Kết quả thực hiện',
        help='Nhà thầu mô tả việc đã thực hiện, kèm ảnh đính kèm.')
    is_overdue = fields.Boolean(
        string='Quá hạn', compute='_compute_is_overdue')
    attachment_ids = fields.Many2many(
        'ir.attachment', string='Ảnh / tài liệu')
    state = fields.Selection([
        ('draft', 'Nháp'),
        ('issued', 'Đã phát hành'),
        ('done', 'Đã thực hiện — chờ nghiệm thu'),
        ('closed', 'Đóng'),
        ('cancelled', 'Huỷ'),
    ], default='draft', string='Trạng thái', tracking=True, copy=False)

    def _compute_is_overdue(self):
        today = fields.Date.context_today(self)
        for rec in self:
            rec.is_overdue = bool(
                rec.deadline and rec.deadline < today
                and rec.state == 'issued')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('code', _('Mới')) == _('Mới'):
                vals['code'] = self.env['ir.sequence'].next_by_code(
                    'rp.site.instruction') or _('Mới')
        return super().create(vals_list)

    def action_issue(self):
        self.write({'state': 'issued',
                    'issued_date': fields.Date.context_today(self)})

    def action_done(self):
        self.write({'state': 'done',
                    'done_date': fields.Date.context_today(self)})

    def action_close(self):
        self.write({'state': 'closed'})

    def action_reopen(self):
        self.write({'state': 'issued', 'done_date': False})

    def action_cancel(self):
        self.write({'state': 'cancelled'})
