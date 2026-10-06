# -*- coding: utf-8 -*-
"""Sổ rút dự phòng.

Luật chịu lực của cả module: **rút dự phòng KHÔNG làm tăng tổng ngân
sách**. Dự phòng đã nằm sẵn trong mốc đã duyệt, nên khi một phát sinh
được tài trợ bằng dự phòng thì tiền chỉ chuyển chỗ — từ dòng dự phòng
sang phần việc — còn tổng thì y nguyên. Chỉ khi dự phòng cạn mà vẫn còn
phát sinh thì tổng mới phải nới, và lúc đó mới là *vượt ngân sách* thật.

Vì vậy số dư dự phòng chính là cảnh báo sớm: nó cạn dần trước khi con số
"vượt" kịp xuất hiện. Dự án nào tiêu hết 80% dự phòng khi mới xong 40%
khối lượng là dự án đang hỏng, dù báo cáo vẫn nói "trong ngân sách".

Số âm là HOÀN LẠI dự phòng (phát sinh bị huỷ, hoặc quyết toán thấp hơn
giá duyệt) — cố ý cho phép, vì tiền quay về quỹ là chuyện có thật.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class RpContingencyDrawdown(models.Model):
    _name = 'rp.contingency.drawdown'
    _description = 'Phiếu rút dự phòng'
    _inherit = ['mail.thread']
    _order = 'date desc, id desc'

    name = fields.Char(
        string='Số phiếu', required=True, copy=False, tracking=True,
        default=lambda self: _('Mới'))
    project_id = fields.Many2one(
        're.project', string='Dự án', required=True, index=True,
        ondelete='cascade', tracking=True)
    date = fields.Date(
        string='Ngày rút', required=True, tracking=True,
        default=fields.Date.context_today)
    amount = fields.Monetary(
        string='Số tiền rút', required=True, tracking=True,
        currency_field='currency_id',
        help='Dương là rút khỏi quỹ dự phòng. ÂM là hoàn lại quỹ — dùng '
             'khi phát sinh bị huỷ hoặc quyết toán thấp hơn giá đã duyệt.')
    source = fields.Selection(
        [('variation', 'Phát sinh'),
         ('claim', 'Khiếu nại / EOT'),
         ('other', 'Khác')],
        string='Nguồn', required=True, default='variation', tracking=True)
    variation_id = fields.Many2one(
        'rp.variation', string='Phát sinh', ondelete='restrict',
        domain="[('project_id', '=', project_id)]", tracking=True)
    reason = fields.Text(
        string='Lý do rút', required=True,
        help='Vì sao khoản này được tài trợ bằng dự phòng chứ không phải '
             'xin nới ngân sách.')
    state = fields.Selection(
        [('draft', 'Nháp'),
         ('confirmed', 'Đã duyệt rút'),
         ('cancelled', 'Huỷ')],
        string='Trạng thái', default='draft', required=True, tracking=True,
        copy=False)
    approved_by_id = fields.Many2one(
        'res.users', string='Người duyệt rút', tracking=True)
    currency_id = fields.Many2one(
        'res.currency', related='project_id.currency_id',
        store=True, readonly=True)
    company_id = fields.Many2one(
        'res.company', string='Công ty',
        default=lambda self: self.env.company, index=True)
    # Số dư quỹ NGAY SAU phiếu này — để đọc sổ là thấy quỹ cạn dần,
    # khỏi phải tự cộng trừ.
    balance_after = fields.Monetary(
        string='Số dư sau phiếu', compute='_compute_balance_after',
        currency_field='currency_id')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('Mới')) == _('Mới'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'rp.contingency.drawdown') or _('Phiếu rút mới')
        return super().create(vals_list)

    def _compute_balance_after(self):
        for rec in self:
            if not rec.project_id:
                rec.balance_after = 0.0
                continue
            truoc = self.search([
                ('project_id', '=', rec.project_id.id),
                ('state', '=', 'confirmed'),
                '|', ('date', '<', rec.date),
                '&', ('date', '=', rec.date), ('id', '<=', rec.id or 0),
            ])
            rec.balance_after = (rec.project_id.contingency_budget
                                 - sum(truoc.mapped('amount')))

    @api.onchange('variation_id')
    def _onchange_variation(self):
        if self.variation_id:
            self.amount = self.variation_id.amount_approved
            if not self.reason:
                self.reason = _(
                    'Tài trợ phát sinh %s bằng quỹ dự phòng.',
                    self.variation_id.display_name)

    def action_duyet_rut(self):
        for rec in self:
            if not rec.amount:
                raise UserError(_(
                    'Phiếu "%s" chưa có số tiền.', rec.name))
            con_lai = rec.project_id.contingency_remaining
            if rec.amount > 0 and rec.amount > con_lai:
                raise UserError(_(
                    'Quỹ dự phòng chỉ còn %(con)s, không rút được '
                    '%(rut)s.\n\nPhần vượt quá quỹ KHÔNG được rút âm '
                    'thầm — nó phải đi đường xin nới ngân sách và chốt '
                    'lại mốc, để còn nhìn thấy.',
                    con='{:,.0f}'.format(con_lai),
                    rut='{:,.0f}'.format(rec.amount)))
            rec.write({'state': 'confirmed',
                       'approved_by_id': self.env.user.id})
        return True

    def action_huy(self):
        self.write({'state': 'cancelled'})
        return True

    def action_ve_nhap(self):
        self.write({'state': 'draft', 'approved_by_id': False})
        return True
