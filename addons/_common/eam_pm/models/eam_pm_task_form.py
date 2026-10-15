# -*- coding: utf-8 -*-
"""Bước kế hoạch bảo trì cũng khai được KIỂU Ô, và chép nguyên sang lệnh.

Khai ở kế hoạch thì mọi lệnh sinh ra đều mang theo tiêu chuẩn máy đọc
được. Khai ở từng lệnh thì người tạo lệnh gấp sẽ bỏ trống — và cổng
kiểm im lặng cho qua đúng những lệnh gấp nhất, cùng một lập luận với
năng lực yêu cầu bên ``eam_competency``.

Chỗ dễ sót: ``_sinh_lenh`` trước đây chỉ chép tên, tiêu chuẩn bằng chữ
và cờ chịu lực. Không chép phần khai kiểu ô thì bước trên lệnh rơi về
ô chữ, và toàn bộ việc "máy tự kết luận" biến mất **mà không báo gì** —
màn hình vẫn đủ các bước, chỉ là không còn kiểm gì nữa.
"""
from odoo import fields, models


class EamPmTask(models.Model):
    _name = 'eam.pm.task'
    _inherit = ['eam.pm.task', 'eam.form.field.mixin']


class EamPmPlan(models.Model):
    _inherit = 'eam.pm.plan'

    form_template_ids = fields.Many2many(
        'eam.form.template', 'eam_pm_plan_form_rel', 'plan_id',
        'template_id', string='Mẫu biểu kèm theo',
        help='Mẫu gắn thêm vào mọi lệnh sinh từ kế hoạch này — ví dụ '
             'phiếu cô lập nguồn. Khác với các bước ở trên: mẫu dùng '
             'chung cho nhiều kế hoạch, sửa một chỗ là đổi tất cả.')


class EamPmSchedule(models.Model):
    _inherit = 'eam.pm.schedule'

    def _sinh_lenh(self):
        w = super()._sinh_lenh()
        p = self.plan_id
        # Chép phần KHAI KIỂU Ô theo từng bước. Khớp theo pm_task_id chứ
        # không theo thứ tự: thứ tự đổi được bất cứ lúc nào, và khớp sai
        # thì tiêu chuẩn của bước này rơi vào bước khác — sai im lặng và
        # rất khó thấy.
        theo_task = {b.pm_task_id.id: b for b in w.step_ids if b.pm_task_id}
        for t in p.task_ids:
            b = theo_task.get(t.id)
            if not b:
                continue
            b.write({
                'field_type': t.field_type,
                'uom_label': t.uom_label,
                'value_min': t.value_min,
                'value_max': t.value_max,
                'selection_values': t.selection_values,
                'requires_photo': t.requires_photo,
            })
        if p.form_template_ids:
            S = self.env['eam.work.order.step']
            tt = max(w.step_ids.mapped('sequence') or [0])
            for m in p.form_template_ids:
                for d in m.line_ids.sorted('sequence'):
                    v = d._sang_buoc()
                    tt += 10
                    v.update({'wo_id': w.id, 'sequence': tt})
                    S.create(v)
        return w
