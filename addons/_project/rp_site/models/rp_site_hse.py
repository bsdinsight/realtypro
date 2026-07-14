# -*- coding: utf-8 -*-
"""HSE hiện trường: kiểm tra an toàn (checklist), toolbox meeting,
sổ sự cố/near-miss."""
from odoo import _, api, fields, models


class RpSiteSafetyInspection(models.Model):
    _name = 'rp.site.safety.inspection'
    _description = 'Kiểm tra an toàn lao động'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(
        string='Số biên bản', required=True, copy=False, readonly=True,
        default=lambda self: _('Mới'))
    date = fields.Date(
        string='Ngày kiểm tra', required=True,
        default=fields.Date.context_today, tracking=True)
    project_id = fields.Many2one(
        're.project', string='Dự án', required=True, index=True)
    contract_id = fields.Many2one(
        'rp.contract', string='HĐ nhà thầu / công trường',
        domain="[('project_id', '=', project_id)]")
    contractor_id = fields.Many2one(
        related='contract_id.contractor_id', string='Nhà thầu',
        store=True, index=True)
    inspector_id = fields.Many2one(
        'res.users', string='Người kiểm tra', required=True,
        default=lambda self: self.env.user)
    line_ids = fields.One2many(
        'rp.site.safety.inspection.line', 'inspection_id',
        string='Nội dung kiểm tra')
    result = fields.Selection([
        ('pass', 'Đạt'),
        ('pass_note', 'Đạt — có kiến nghị'),
        ('fail', 'Không đạt'),
    ], string='Kết quả chung', tracking=True)
    findings = fields.Text(
        string='Phát hiện / kiến nghị',
        help='Tồn tại về an toàn cần khắc phục — có thể chuyển thành '
             'punch list để theo dõi vòng đời xử lý.')
    attachment_ids = fields.Many2many('ir.attachment', string='Ảnh')
    state = fields.Selection([
        ('draft', 'Nháp'), ('done', 'Hoàn tất'),
    ], default='draft', string='Trạng thái', tracking=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('Mới')) == _('Mới'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'rp.site.safety.inspection') or _('Mới')
        return super().create(vals_list)

    def action_done(self):
        self.write({'state': 'done'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})


class RpSiteSafetyInspectionLine(models.Model):
    _name = 'rp.site.safety.inspection.line'
    _description = 'Kiểm tra an toàn — dòng checklist'
    _order = 'id'

    inspection_id = fields.Many2one(
        'rp.site.safety.inspection', required=True, ondelete='cascade')
    name = fields.Char(string='Hạng mục kiểm tra', required=True)
    result = fields.Selection([
        ('ok', 'Đạt'),
        ('not_ok', 'Không đạt'),
        ('na', 'Không áp dụng'),
    ], default='ok', string='Kết quả')
    note = fields.Char(string='Ghi chú')


class RpSiteToolbox(models.Model):
    _name = 'rp.site.toolbox'
    _description = 'Toolbox meeting (họp an toàn đầu giờ)'
    _inherit = ['mail.thread']
    _order = 'date desc, id desc'

    name = fields.Char(string='Chủ đề', required=True)
    date = fields.Date(
        string='Ngày', required=True, default=fields.Date.context_today)
    project_id = fields.Many2one(
        're.project', string='Dự án', required=True, index=True)
    contract_id = fields.Many2one(
        'rp.contract', string='HĐ nhà thầu / công trường',
        domain="[('project_id', '=', project_id)]")
    presenter_id = fields.Many2one(
        'res.users', string='Người chủ trì',
        default=lambda self: self.env.user)
    contractor_id = fields.Many2one(
        'res.partner', string='Nhà thầu tham dự',
        domain=[('is_company', '=', True)])
    attendee_count = fields.Integer(string='Số người tham dự')
    notes = fields.Text(string='Nội dung phổ biến')
    attachment_ids = fields.Many2many('ir.attachment', string='Ảnh')


class RpSiteIncident(models.Model):
    _name = 'rp.site.incident'
    _description = 'Sự cố / near-miss an toàn lao động'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    code = fields.Char(
        string='Mã', required=True, copy=False, readonly=True,
        default=lambda self: _('Mới'))
    name = fields.Char(string='Sự việc', required=True, tracking=True)
    date = fields.Datetime(
        string='Thời điểm', required=True, default=fields.Datetime.now)
    project_id = fields.Many2one(
        're.project', string='Dự án', required=True, index=True)
    contract_id = fields.Many2one(
        'rp.contract', string='HĐ nhà thầu / công trường',
        domain="[('project_id', '=', project_id)]")
    contractor_id = fields.Many2one(
        related='contract_id.contractor_id', string='Nhà thầu',
        store=True, index=True)
    incident_type = fields.Selection([
        ('near_miss', 'Near-miss (suýt xảy ra)'),
        ('minor', 'Nhẹ (sơ cứu tại chỗ)'),
        ('lost_time', 'Mất ngày công (LTI)'),
        ('serious', 'Nghiêm trọng'),
    ], required=True, default='near_miss', string='Phân loại',
        tracking=True)
    location = fields.Char(string='Vị trí')
    people_involved = fields.Char(string='Người liên quan')
    description = fields.Text(string='Diễn biến')
    immediate_action = fields.Text(string='Xử lý tức thời')
    corrective_action = fields.Text(string='Hành động khắc phục/phòng ngừa')
    attachment_ids = fields.Many2many('ir.attachment', string='Ảnh')
    state = fields.Selection([
        ('reported', 'Ghi nhận'),
        ('investigating', 'Đang điều tra'),
        ('closed', 'Đóng'),
    ], default='reported', string='Trạng thái', tracking=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('code', _('Mới')) == _('Mới'):
                vals['code'] = self.env['ir.sequence'].next_by_code(
                    'rp.site.incident') or _('Mới')
        return super().create(vals_list)

    def action_investigate(self):
        self.write({'state': 'investigating'})

    def action_close(self):
        self.write({'state': 'closed'})
