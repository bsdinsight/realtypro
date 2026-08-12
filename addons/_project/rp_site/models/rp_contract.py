# -*- coding: utf-8 -*-
"""HĐ nhà thầu: smart button hiện trường — nhật ký + punch đang mở."""
from odoo import _, fields, models


class RpContract(models.Model):
    _inherit = 'rp.contract'

    site_diary_count = fields.Integer(compute='_compute_site_counts')
    open_punch_count = fields.Integer(
        compute='_compute_site_counts',
        help='Punch (lỗi hiện trường) chưa đóng — cân nhắc trước khi '
             'nghiệm thu / thanh toán.')

    def _compute_site_counts(self):
        Diary = self.env['rp.site.diary']
        Punch = self.env['rp.site.punch']
        for c in self:
            c.site_diary_count = Diary.search_count(
                [('contract_id', '=', c.id)])
            c.open_punch_count = Punch.search_count(
                [('contract_id', '=', c.id),
                 ('state', 'in', ('open', 'in_progress', 'fixed'))])

    def action_view_site_diaries(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'target': 'new',
            'name': _('Nhật ký thi công — %s', self.name),
            'res_model': 'rp.site.diary',
            'view_mode': 'list,form',
            'domain': [('contract_id', '=', self.id)],
            'context': {'default_contract_id': self.id,
                        'default_project_id': self.project_id.id},
        }

    def action_view_punches(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'target': 'new',
            'name': _('Punch list — %s', self.name),
            'res_model': 'rp.site.punch',
            'view_mode': 'list,form',
            'domain': [('contract_id', '=', self.id)],
            'context': {'default_contract_id': self.id,
                        'default_project_id': self.project_id.id,
                        'search_default_filter_open': 1},
        }
