# -*- coding: utf-8 -*-
"""Biên bản tính phạt chậm — đóng băng số liệu tại ngày chốt.

Con số phạt trên form hợp đồng là DỰ BÁO: nó đổi mỗi khi lịch đổi. Lúc
làm việc với nhà thầu thì phải có một con số đứng yên, kèm căn cứ: chốt
ngày nào, mốc hợp đồng sau gia hạn là ngày nào, chậm bao nhiêu ngày,
mức phạt bao nhiêu, trần bao nhiêu. Bản ghi này giữ đúng những thứ đó
và không tự đổi theo lịch nữa.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class RpLdAssessment(models.Model):
    _name = 'rp.ld.assessment'
    _description = 'Biên bản tính phạt chậm tiến độ'
    _inherit = ['mail.thread']
    _order = 'date_cutoff desc, id desc'

    name = fields.Char(string='Số biên bản', copy=False, readonly=True,
                       index=True)
    contract_id = fields.Many2one(
        'rp.contract', string='Hợp đồng', required=True, index=True,
        ondelete='cascade', tracking=True)
    project_id = fields.Many2one(
        're.project', related='contract_id.project_id', store=True)
    partner_id = fields.Many2one(
        'res.partner', related='contract_id.contractor_id', store=True,
        string='Nhà thầu')
    currency_id = fields.Many2one(
        'res.currency', related='contract_id.currency_id', store=True)

    date_cutoff = fields.Date(
        string='Ngày chốt', required=True, tracking=True,
        default=fields.Date.context_today)
    date_due = fields.Date(string='Hoàn thành theo HĐ (đã gia hạn)',
                           tracking=True)
    date_actual = fields.Date(
        string='Hoàn thành thực tế / dự báo', tracking=True)
    eot_days_granted = fields.Integer(string='Ngày đã gia hạn')
    days_late = fields.Integer(string='Số ngày chậm', tracking=True)
    rate_per_day = fields.Float(string='Mức phạt (%/ngày)', digits=(5, 4))
    cap_percent = fields.Float(string='Trần phạt (%)', digits=(5, 2))
    base_amount = fields.Monetary(string='Giá trị căn cứ')
    amount = fields.Monetary(string='Tiền phạt', tracking=True)
    capped = fields.Boolean(string='Đã chạm trần')
    note = fields.Text(string='Ghi chú')

    state = fields.Selection(
        [('draft', 'Dự thảo'),
         ('notified', 'Đã thông báo nhà thầu'),
         ('deducted', 'Đã khấu trừ thanh toán'),
         ('waived', 'Miễn / giảm')],
        string='Trạng thái', default='draft', required=True, tracking=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'rp.ld.assessment') or '/'
        records = super().create(vals_list)
        records._snapshot()
        return records

    def _snapshot(self):
        """Chụp số liệu từ hợp đồng tại thời điểm lập."""
        for rec in self:
            c = rec.contract_id
            rec.write({
                'date_due': c.date_completion_adjusted,
                'date_actual': c.ld_forecast_end,
                'eot_days_granted': c.eot_days_granted,
                'days_late': c.ld_days_late,
                'rate_per_day': c.ld_rate_per_day,
                'cap_percent': c.ld_cap_percent,
                'base_amount': c.ld_base_amount,
                'amount': c.ld_amount_exposure,
                'capped': c.ld_capped,
            })

    def action_refresh(self):
        """Chụp lại theo số hiện tại — chỉ khi còn là dự thảo."""
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_(
                    'Biên bản đã thông báo hoặc đã khấu trừ thì không '
                    'cập nhật lại được. Lập biên bản mới cho kỳ sau.'))
        self._snapshot()
        self.write({'date_cutoff': fields.Date.context_today(self)})

    def action_notify(self):
        self.write({'state': 'notified'})

    def action_deduct(self):
        self.write({'state': 'deducted'})

    def action_waive(self):
        self.write({'state': 'waived'})
