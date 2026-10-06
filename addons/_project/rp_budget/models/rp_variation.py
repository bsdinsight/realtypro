# -*- coding: utf-8 -*-
"""Nút tài trợ một phát sinh bằng quỹ dự phòng.

Đặt nút ngay trên phát sinh vì đó là lúc người ta thực sự quyết định:
duyệt xong một phát sinh thì câu hỏi kế tiếp luôn là "tiền ở đâu ra" —
lấy từ dự phòng, hay phải xin nới ngân sách. Bắt họ sang màn khác để
trả lời câu đó thì phần lớn sẽ không trả lời, và quỹ dự phòng thành
một con số chết.
"""
from odoo import _, fields, models
from odoo.exceptions import UserError


class RpVariation(models.Model):
    _inherit = 'rp.variation'

    drawdown_ids = fields.One2many(
        'rp.contingency.drawdown', 'variation_id', string='Phiếu rút dự phòng')
    drawdown_amount = fields.Monetary(
        string='Đã lấy từ dự phòng', compute='_compute_drawdown_amount',
        currency_field='currency_id')

    def _compute_drawdown_amount(self):
        for rec in self:
            rec.drawdown_amount = sum(rec.drawdown_ids.filtered(
                lambda d: d.state == 'confirmed').mapped('amount'))

    def action_rut_du_phong(self):
        """Lập phiếu rút dự phòng cho phần giá trị chưa được tài trợ."""
        self.ensure_one()
        if self.state not in ('approved', 'instructed', 'applied'):
            raise UserError(_(
                'Chỉ phát sinh ĐÃ DUYỆT GIÁ mới rút dự phòng được. '
                'Phát sinh này đang ở "%s".',
                dict(self._fields['state'].selection).get(self.state)))
        con_thieu = (self.amount_approved or 0.0) - self.drawdown_amount
        if not con_thieu:
            raise UserError(_(
                'Phát sinh này đã được tài trợ đủ bằng dự phòng rồi.'))
        phieu = self.env['rp.contingency.drawdown'].create({
            'project_id': self.project_id.id,
            'variation_id': self.id,
            'source': 'variation',
            'amount': con_thieu,
            'reason': _('Tài trợ phát sinh %s bằng quỹ dự phòng.',
                        self.display_name),
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Phiếu rút dự phòng'),
            'res_model': 'rp.contingency.drawdown',
            'res_id': phieu.id,
            'view_mode': 'form',
            'target': 'new',
        }
