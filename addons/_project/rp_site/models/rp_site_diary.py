# -*- coding: utf-8 -*-
"""rp.site.diary — Nhật ký thi công (hồ sơ bắt buộc, NĐ 06/2021).

Mỗi ngày × công trường (HĐ nhà thầu) một nhật ký: thời tiết, nhân lực,
máy móc, công việc thực hiện (link task lịch thi công), vật tư, vướng
mắc/chỉ đạo, ảnh hiện trường. Luồng: Lập → Trình → Xác nhận (TVGS/CĐT).
Nhật ký đã xác nhận là input cho Trợ lý AI đọc tiến độ (rp_ai).
"""
from odoo import _, api, fields, models

WEATHER = [
    ('sunny', 'Nắng'),
    ('cloudy', 'Nhiều mây'),
    ('light_rain', 'Mưa nhỏ'),
    ('heavy_rain', 'Mưa to'),
    ('storm', 'Bão / thời tiết cực đoan'),
]


class RpSiteDiary(models.Model):
    _name = 'rp.site.diary'
    _description = 'Nhật ký thi công'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(
        string='Số nhật ký', required=True, copy=False,
        readonly=True, default=lambda self: _('Mới'))
    date = fields.Date(
        string='Ngày', required=True, default=fields.Date.context_today,
        tracking=True)
    project_id = fields.Many2one(
        're.project', string='Dự án', required=True, index=True,
        tracking=True)
    contract_id = fields.Many2one(
        'rp.contract', string='HĐ nhà thầu / công trường', index=True,
        domain="[('project_id', '=', project_id)]", tracking=True)
    weather_am = fields.Selection(WEATHER, string='Thời tiết sáng')
    weather_pm = fields.Selection(WEATHER, string='Thời tiết chiều')

    manpower_ids = fields.One2many(
        'rp.site.diary.manpower', 'diary_id', string='Nhân lực')
    equipment_ids = fields.One2many(
        'rp.site.diary.equipment', 'diary_id', string='Máy móc thiết bị')
    work_ids = fields.One2many(
        'rp.site.diary.work', 'diary_id', string='Công việc thực hiện')

    total_manpower = fields.Integer(
        string='Tổng nhân lực', compute='_compute_total_manpower',
        store=True)
    materials_note = fields.Text(
        string='Vật tư về công trường',
        help='Vật tư, thiết bị nhập về công trường trong ngày.')
    issues = fields.Text(
        string='Vướng mắc / tồn tại',
        help='Vấn đề phát sinh, vướng mắc cần xử lý.')
    instructions = fields.Text(
        string='Ý kiến chỉ đạo (TVGS/CĐT)',
        help='Chỉ đạo của tư vấn giám sát / chủ đầu tư trong ngày.')
    attachment_ids = fields.Many2many(
        'ir.attachment', string='Ảnh hiện trường')

    user_id = fields.Many2one(
        'res.users', string='Người lập', required=True,
        default=lambda self: self.env.user, tracking=True)
    confirmed_by_id = fields.Many2one(
        'res.users', string='Người xác nhận', readonly=True, copy=False)
    confirmed_date = fields.Datetime(
        string='Xác nhận lúc', readonly=True, copy=False)
    state = fields.Selection([
        ('draft', 'Nháp'),
        ('submitted', 'Chờ xác nhận'),
        ('confirmed', 'Đã xác nhận'),
    ], default='draft', string='Trạng thái', tracking=True, copy=False)

    _uniq_diary_per_day = models.Constraint(
        'unique(project_id, contract_id, date)',
        'Mỗi ngày chỉ có một nhật ký cho một công trường (HĐ).')

    @api.depends('manpower_ids.headcount')
    def _compute_total_manpower(self):
        for rec in self:
            rec.total_manpower = sum(rec.manpower_ids.mapped('headcount'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('Mới')) == _('Mới'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'rp.site.diary') or _('Mới')
        return super().create(vals_list)

    def action_submit(self):
        self.write({'state': 'submitted'})

    def action_confirm(self):
        self.write({
            'state': 'confirmed',
            'confirmed_by_id': self.env.user.id,
            'confirmed_date': fields.Datetime.now(),
        })

    def action_reset_draft(self):
        self.write({'state': 'draft', 'confirmed_by_id': False,
                    'confirmed_date': False})


class RpSiteDiaryManpower(models.Model):
    _name = 'rp.site.diary.manpower'
    _description = 'Nhật ký — nhân lực'
    _order = 'id'

    diary_id = fields.Many2one(
        'rp.site.diary', required=True, ondelete='cascade')
    contractor_id = fields.Many2one(
        'res.partner', string='Nhà thầu / đơn vị',
        domain=[('is_company', '=', True)])
    trade = fields.Char(
        string='Đội / nghề', help='Vd: đội cốt thép, đội cốp pha, đội hàn.')
    headcount = fields.Integer(string='Số người', default=0)
    note = fields.Char(string='Ghi chú')


class RpSiteDiaryEquipment(models.Model):
    _name = 'rp.site.diary.equipment'
    _description = 'Nhật ký — máy móc thiết bị'
    _order = 'id'

    diary_id = fields.Many2one(
        'rp.site.diary', required=True, ondelete='cascade')
    name = fields.Char(string='Thiết bị', required=True)
    quantity = fields.Integer(string='Số lượng', default=1)
    status = fields.Selection([
        ('working', 'Hoạt động'),
        ('idle', 'Chờ việc'),
        ('broken', 'Hỏng / sửa chữa'),
    ], default='working', string='Tình trạng')
    note = fields.Char(string='Ghi chú')


class RpSiteDiaryWork(models.Model):
    _name = 'rp.site.diary.work'
    _description = 'Nhật ký — công việc thực hiện'
    _order = 'id'

    diary_id = fields.Many2one(
        'rp.site.diary', required=True, ondelete='cascade')
    task_id = fields.Many2one(
        'project.task', string='Công việc (lịch thi công)',
        domain="[('rp_contract_id', '=', parent.contract_id)]")
    structure_id = fields.Many2one(
        'rp.structure', string='Hạng mục',
        domain="[('project_id', '=', parent.project_id)]")
    description = fields.Char(string='Nội dung thực hiện', required=True)
    progress_note = fields.Char(
        string='Khối lượng / tiến độ',
        help='Vd: "ép 12 cọc D600", "đổ 180 m³ bê tông sàn T3".')
