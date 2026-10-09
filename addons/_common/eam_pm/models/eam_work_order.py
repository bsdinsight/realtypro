# -*- coding: utf-8 -*-
from odoo import api, fields, models


class EamWorkOrder(models.Model):
    """Lệnh sinh từ kế hoạch bảo trì — và làm xong thì đẩy đồng hồ chạy tiếp."""
    _inherit = 'eam.work.order'

    pm_plan_id = fields.Many2one(
        'eam.pm.plan', string='Theo kế hoạch bảo trì', ondelete='set null',
        index=True, readonly=True)
    pm_schedule_id = fields.Many2one(
        'eam.pm.schedule', string='Dòng lịch bảo trì', ondelete='set null',
        index=True, readonly=True)
    is_pm = fields.Boolean(
        string='Sinh từ kế hoạch', compute='_compute_is_pm', store=True)

    @api.depends('pm_plan_id')
    def _compute_is_pm(self):
        for w in self:
            w.is_pm = bool(w.pm_plan_id)

    def action_xong(self):
        """Chốt lệnh, rồi ĐẨY ĐỒNG HỒ BẢO TRÌ CHẠY TIẾP.

        Đây là chỗ vòng khép lại, và cũng là chỗ dễ quên nhất: không ghi
        lại ngày làm xong và số đồng hồ tại thời điểm đó thì chu kỳ sau
        vẫn đếm từ lần trước nữa — kế hoạch lập tức quá hạn lại, cron
        sinh lệnh mới, và người dùng thấy cùng một việc hiện ra mãi.
        """
        r = super().action_xong()
        for w in self.filtered('pm_schedule_id'):
            w.pm_schedule_id._dong_ho_chay_tiep(
                w.date_end and w.date_end.date()
                or fields.Date.context_today(w))
        return r
