# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta

from odoo import _, fields, models
from odoo.exceptions import UserError


class RpErectionGenerate(models.TransientModel):
    """Sinh sổ dựng máy: mỗi vị trí × mỗi cổng một dòng.

    Chạy lại được nhiều lần mà không hỏng dữ liệu: chỉ TẠO ô còn thiếu,
    không đụng ô đã có. Thêm một cổng mới giữa chừng là chuyện bình
    thường của dự án, và lúc đó phải sinh bù cho cả đội vị trí mà không
    xoá mất những gì đã ghi.
    """
    _name = 'rp.erection.generate'
    _description = 'Sinh sổ dựng máy'

    plant_id = fields.Many2one(
        'eam.location', string='Nhà máy', required=True,
        domain="[('location_type', '=', 'plant')]")
    gate_ids = fields.Many2many(
        'rp.erection.gate', string='Cổng áp dụng',
        default=lambda s: s.env['rp.erection.gate'].search([]).ids)
    date_start = fields.Date(
        string='Mốc bắt đầu kế hoạch',
        help='Để trống thì không điền ngày kế hoạch.')
    days_per_gate = fields.Integer(
        string='Số ngày mỗi cổng', default=14,
        help='Cách rải THÔ cho bản nháp — mọi vị trí cùng một lịch. Thực '
             'tế mỗi trụ một tiến độ khác nhau, nên ngày thật phải sửa '
             'trên từng ô hoặc nhập từ lịch của nhà thầu.')

    def action_sinh(self):
        self.ensure_one()
        if not self.gate_ids:
            raise UserError(_('Chưa chọn cổng nào.'))
        L = self.env['eam.location']
        S = self.env['rp.erection.step']
        vt = L.search([('id', 'child_of', self.plant_id.id),
                       ('location_type', '=', 'position')])
        if not vt:
            raise UserError(_(
                'Nhà máy "%s" chưa có vị trí thiết bị nào.',
                self.plant_id.display_name))

        cong = self.gate_ids.sorted('sequence')
        da_co = {(s.location_id.id, s.gate_id.id)
                 for s in S.search([('location_id', 'in', vt.ids)])}
        moi = []
        for l in vt:
            for buoc, g in enumerate(cong):
                if (l.id, g.id) in da_co:
                    continue
                v = {'location_id': l.id, 'gate_id': g.id}
                if self.date_start:
                    v['date_plan'] = self.date_start + relativedelta(
                        days=buoc * (self.days_per_gate or 0))
                moi.append(v)
        S.create(moi)
        return {
            'type': 'ir.actions.act_window',
            'name': _('Sổ dựng máy — %s', self.plant_id.name or ''),
            'res_model': 'rp.erection.step',
            'view_mode': 'list,form',
            'domain': [('location_id', 'in', vt.ids)],
            'context': {'search_default_g_vitri': 1},
        }
