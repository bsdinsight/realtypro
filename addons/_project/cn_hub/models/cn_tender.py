# -*- coding: utf-8 -*-
"""Gói thầu công bố lên Network + hồ sơ dự thầu của nhà thầu."""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class CnTender(models.Model):
    _name = 'cn.tender'
    _description = 'Gói thầu (Construction Network)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'deadline, id desc'

    name = fields.Char(string='Tên gói thầu', required=True, tracking=True)
    ref = fields.Char(
        string='Mã tham chiếu', copy=False, index=True,
        help='Mã gói thầu bên tổng thầu (đồng bộ qua connector).')
    gc_partner_id = fields.Many2one(
        'res.partner', string='Tổng thầu / Chủ đầu tư', tracking=True,
        help='Đơn vị công bố gói thầu.')
    gc_source = fields.Char(
        string='Nguồn (tenant)', help='Định danh hệ thống tổng thầu gửi lên.')
    description = fields.Text(string='Mô tả / phạm vi')
    specialty = fields.Char(string='Chuyên môn cần', index=True)
    budget = fields.Monetary(string='Dự toán / giá gói')
    currency_id = fields.Many2one(
        'res.currency', default=lambda self: self.env.company.currency_id)
    date_open = fields.Date(string='Ngày mở', default=fields.Date.context_today)
    deadline = fields.Date(string='Hạn nộp')
    state = fields.Selection(
        [('draft', 'Nháp'),
         ('open', 'Đang mời thầu'),
         ('closed', 'Đã đóng thầu'),
         ('awarded', 'Đã trao thầu'),
         ('cancelled', 'Đã hủy')],
        string='Trạng thái', default='draft', required=True, tracking=True)
    bid_ids = fields.One2many('cn.bid', 'tender_id', string='Hồ sơ dự thầu')
    bid_count = fields.Integer(compute='_compute_bid_count')
    awarded_bid_id = fields.Many2one(
        'cn.bid', string='Hồ sơ trúng thầu', copy=False)
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company)

    def _compute_bid_count(self):
        data = self.env['cn.bid']._read_group(
            [('tender_id', 'in', self.ids)], groupby=['tender_id'],
            aggregates=['__count'])
        mapped = {t.id: c for t, c in data}
        for rec in self:
            rec.bid_count = mapped.get(rec.id, 0)

    def action_open(self):
        self.write({'state': 'open'})

    def action_close(self):
        self.write({'state': 'closed'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_view_bids(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Hồ sơ dự thầu — %s', self.name),
            'res_model': 'cn.bid',
            'view_mode': 'list,form',
            'domain': [('tender_id', '=', self.id)],
            'context': {'default_tender_id': self.id},
        }


class CnBid(models.Model):
    _name = 'cn.bid'
    _description = 'Hồ sơ dự thầu (Construction Network)'
    _inherit = ['mail.thread']
    _order = 'price, id'

    tender_id = fields.Many2one(
        'cn.tender', string='Gói thầu', required=True, ondelete='cascade',
        index=True)
    contractor_id = fields.Many2one(
        'res.partner', string='Nhà thầu', required=True, tracking=True,
        index=True)
    price = fields.Monetary(string='Giá dự thầu', tracking=True)
    currency_id = fields.Many2one(related='tender_id.currency_id')
    note = fields.Text(string='Thuyết minh')
    doc = fields.Binary(string='Hồ sơ (file)')
    doc_filename = fields.Char()
    date_submit = fields.Datetime(
        string='Ngày nộp', default=fields.Datetime.now)
    state = fields.Selection(
        [('submitted', 'Đã nộp'),
         ('shortlisted', 'Vào danh sách ngắn'),
         ('awarded', 'Trúng thầu'),
         ('rejected', 'Bị loại')],
        string='Trạng thái', default='submitted', required=True,
        tracking=True)
    company_id = fields.Many2one(related='tender_id.company_id', store=True)

    _sql_constraints = [
        ('uniq_bid', 'unique(tender_id, contractor_id)',
         'Mỗi nhà thầu chỉ nộp 1 hồ sơ / gói thầu.'),
    ]

    def action_award(self):
        for bid in self:
            if bid.tender_id.state not in ('open', 'closed'):
                raise UserError(_(
                    'Chỉ trao thầu khi gói đang mời/đã đóng thầu.'))
            bid.state = 'awarded'
            bid.tender_id.write({
                'state': 'awarded', 'awarded_bid_id': bid.id})
            (bid.tender_id.bid_ids - bid).filtered(
                lambda b: b.state != 'rejected').write({'state': 'rejected'})

    def action_shortlist(self):
        self.write({'state': 'shortlisted'})

    def action_reject(self):
        self.write({'state': 'rejected'})
