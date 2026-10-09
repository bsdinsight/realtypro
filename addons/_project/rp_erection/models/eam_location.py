# -*- coding: utf-8 -*-
from odoo import _, api, fields, models


class EamLocation(models.Model):
    """Tiến độ dựng máy gộp về từng vị trí, và bơm lên bản đồ."""
    _inherit = 'eam.location'

    erection_step_ids = fields.One2many(
        'rp.erection.step', 'location_id', string='Sổ dựng máy')
    erection_percent = fields.Float(
        string='% dựng máy', compute='_compute_erection', store=True,
        digits=(16, 1), aggregator=False,
        help='Tính theo TRỌNG SỐ cổng, không phải đếm số cổng. Đổ móng '
             'nặng hơn hẳn đấu một đầu cáp.')
    erection_gate_id = fields.Many2one(
        'rp.erection.gate', string='Đang ở cổng',
        compute='_compute_erection', store=True,
        help='Cổng chưa xong đầu tiên theo thứ tự thi công.')
    erection_blocked = fields.Boolean(
        string='Đang kẹt', compute='_compute_erection', store=True)
    erection_blocked_why = fields.Char(
        string='Kẹt vì', compute='_compute_erection', store=True)
    erection_days_late = fields.Integer(
        string='Trễ nhất (ngày)', compute='_compute_erection', store=True,
        aggregator=False)
    erection_out_of_order = fields.Integer(
        string='Cổng ghi lệch thứ tự', compute='_compute_erection',
        store=True)

    @api.depends('erection_step_ids.state', 'erection_step_ids.days_late',
                 'erection_step_ids.blocked_reason',
                 'erection_step_ids.out_of_order',
                 'erection_step_ids.gate_id.weight',
                 'erection_step_ids.gate_id.sequence')
    def _compute_erection(self):
        for l in self:
            ds = l.erection_step_ids
            tong = sum(ds.mapped('gate_id.weight'))
            xong = sum(s.gate_id.weight for s in ds if s.state == 'done')
            l.erection_percent = (xong / tong * 100.0) if tong else 0.0
            chua = ds.filtered(lambda s: s.state != 'done').sorted(
                lambda s: s.gate_sequence)
            l.erection_gate_id = chua[:1].gate_id
            ket = ds.filtered(lambda s: s.state == 'blocked')[:1]
            l.erection_blocked = bool(ket)
            l.erection_blocked_why = (
                dict(ket._fields['blocked_reason'].selection).get(
                    ket.blocked_reason) if ket else False)
            l.erection_days_late = max(
                (s.days_late for s in chua), default=0)
            l.erection_out_of_order = len(ds.filtered('out_of_order'))

    # ------------------------------------------------------------------
    def _map_payload_one(self, tu, den):
        """Bơm tiến độ dựng máy vào gói dữ liệu của bản đồ.

        Dùng khoá ``extra`` — danh sách dòng tự do mà lõi bản đồ chỉ việc
        bày ra. Nhờ vậy lõi không cần biết gì về dựng máy, và gói ngành
        khác bơm thứ khác vào cùng chỗ.
        """
        d = super()._map_payload_one(tu, den)
        if not self.erection_step_ids:
            return d
        d['erect_pct'] = round(self.erection_percent, 1)
        dong = [{'label': 'Dựng máy',
                 'value': '%.0f%%' % self.erection_percent}]
        if self.erection_gate_id:
            dong.append({'label': 'Đang ở cổng',
                         'value': self.erection_gate_id.name})
        if self.erection_blocked:
            dong.append({'label': 'ĐANG KẸT',
                         'value': self.erection_blocked_why or '—',
                         'warn': True})
        if self.erection_days_late:
            dong.append({'label': 'Trễ', 'warn': True,
                         'value': '%d ngày' % self.erection_days_late})
        if self.erection_out_of_order:
            dong.append({'label': 'Ghi lệch thứ tự', 'warn': True,
                         'value': '%d cổng' % self.erection_out_of_order})
        d.setdefault('extra', []).extend(dong)
        return d

    def action_mo_so_dung_may(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Sổ dựng máy — %s', self.code or ''),
            'res_model': 'rp.erection.step',
            'view_mode': 'list,form',
            'domain': [('location_id', '=', self.id)],
            'context': {'default_location_id': self.id},
        }
