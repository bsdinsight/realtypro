# -*- coding: utf-8 -*-
"""Năng lực yêu cầu khai ở KẾ HOẠCH, không khai lại ở từng lệnh.

Một kế hoạch bảo dưỡng sinh ra hàng chục lệnh mỗi năm trên hàng chục
trụ. Khai chứng chỉ bắt buộc ở từng lệnh là vừa mất công vừa không
chống được sai sót — người tạo lệnh gấp sẽ bỏ trống, và cổng năng lực
im lặng cho qua đúng những lệnh gấp nhất.

Nên nó thuộc về kế hoạch: khai một lần, mọi lệnh sinh ra đều mang theo.
"""
from odoo import fields, models


class EamPmPlan(models.Model):
    _inherit = 'eam.pm.plan'

    skill_ids = fields.Many2many(
        'hr.skill', 'eam_pm_plan_skill_rel', 'plan_id', 'skill_id',
        string='Năng lực yêu cầu',
        help='Chứng chỉ, giấy phép, kỹ năng mà người làm phải có. Mọi lệnh '
             'sinh từ kế hoạch này đều mang theo danh sách này.')


class EamPmSchedule(models.Model):
    _inherit = 'eam.pm.schedule'

    def _sinh_lenh(self):
        w = super()._sinh_lenh()
        if self.plan_id.skill_ids:
            w.skill_ids = [(6, 0, self.plan_id.skill_ids.ids)]
        return w
