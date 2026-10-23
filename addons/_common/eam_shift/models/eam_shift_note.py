# -*- coding: utf-8 -*-
"""Việc và ghi chú trong ca — thứ hay rơi giữa hai ca nhất.

Vì sao KHÔNG chỉ hiện "lệnh công việc còn mở"
----------------------------------------------
Phần mềm hay làm đúng thế, và nó bỏ sót đúng những thứ hay rơi nhất:
lời dặn miệng, cái vừa phát hiện cuối ca chưa kịp lập lệnh, cái đang chờ
nhà thầu trả lời. Những thứ đó không phải lệnh công việc, nhưng chúng là
phần lớn nội dung một cuộc giao ca thật.

Nên ở đây mỗi việc là một dòng **tự do**, nối tuỳ chọn tới lệnh công
việc nếu có. Không ép mọi thứ phải thành lệnh trước khi được ghi nhận.

Sợi dây truy việc bị đùn
-------------------------
Việc chưa xong khi giao ca được **nhân bản sang ca sau**, bản mới trỏ
ngược về bản cũ. Đi ngược sợi dây đó là biết việc này đã lăn qua mấy ca.
Một việc lăn năm ca không phải việc khó — nó là việc đang bị đùn, và
không có con số này thì không ai nhìn thấy.
"""
from odoo import _, api, fields, models


class EamShiftNote(models.Model):
    _name = 'eam.shift.note'
    _description = 'Việc / ghi chú trong ca'
    _order = 'shift_id, muc_do desc, id'

    shift_id = fields.Many2one(
        'eam.shift', string='Ca', required=True, ondelete='cascade',
        index=True)
    plant_id = fields.Many2one(related='shift_id.plant_id', store=True)
    company_id = fields.Many2one(related='shift_id.company_id', store=True)
    ngay = fields.Date(related='shift_id.ngay', store=True)

    name = fields.Char(string='Việc / ghi chú', required=True)
    mo_ta = fields.Text(string='Diễn giải')
    loai = fields.Selection(
        [('trong_ca', 'Phát sinh trong ca'),
         ('ke_hoach', 'Theo kế hoạch'),
         ('chuyen_ca', 'Chuyển từ ca trước')],
        string='Loại', default='trong_ca', required=True, index=True)
    muc_do = fields.Selection(
        [('thap', 'Thường'), ('cao', 'Cần chú ý'), ('khan', 'Khẩn')],
        string='Mức độ', default='thap', required=True)

    location_id = fields.Many2one(
        'eam.location', string='Vị trí / thiết bị', ondelete='set null',
        index=True)
    work_order_id = fields.Many2one(
        'eam.work.order', string='Lệnh công việc', ondelete='set null',
        help='Để trống cũng được. Nhiều thứ cần bàn giao chưa kịp thành '
             'lệnh công việc — ép phải có lệnh trước khi ghi là đúng cách '
             'làm chúng biến mất.')

    state = fields.Selection(
        [('mo', 'Còn mở'),
         ('dang_lam', 'Đang làm'),
         ('cho', 'Đang chờ bên ngoài'),
         ('xong', 'Xong')],
        string='Tình trạng', default='mo', required=True, index=True)

    # ----- Sợi dây truy việc bị đùn -----------------------------------
    nguon_id = fields.Many2one(
        'eam.shift.note', string='Chuyển từ việc', ondelete='set null',
        index=True, copy=False)
    so_ca_da_lan = fields.Integer(
        string='Đã lăn qua (ca)', compute='_compute_lan', store=True,
        recursive=True,
        help='Đếm ngược theo sợi dây chuyển ca. Từ ba ca trở lên là việc '
             'đang bị đùn, không phải việc khó.')
    bi_dun = fields.Boolean(
        string='Đang bị đùn', compute='_compute_lan', store=True,
        recursive=True)

    @api.depends('nguon_id', 'nguon_id.so_ca_da_lan')
    def _compute_lan(self):
        for rec in self:
            rec.so_ca_da_lan = (rec.nguon_id.so_ca_da_lan + 1
                                if rec.nguon_id else 0)
            rec.bi_dun = rec.so_ca_da_lan >= 3

    def action_xem_goc(self):
        """Đi ngược sợi dây tới việc gốc."""
        self.ensure_one()
        goc = self
        while goc.nguon_id:
            goc = goc.nguon_id
        return {
            'type': 'ir.actions.act_window',
            'name': _('Việc gốc — ca %s', goc.shift_id.display_name),
            'res_model': 'eam.shift',
            'res_id': goc.shift_id.id,
            'view_mode': 'form',
        }


class EamShiftSnapshot(models.Model):
    _name = 'eam.shift.snapshot'
    _description = 'Trạng thái thiết bị lúc mở ca'
    _order = 'shift_id, location_id'

    shift_id = fields.Many2one(
        'eam.shift', string='Ca', required=True, ondelete='cascade',
        index=True)
    location_id = fields.Many2one(
        'eam.location', string='Vị trí', required=True, ondelete='cascade')
    company_id = fields.Many2one(related='shift_id.company_id', store=True)

    dang_dung = fields.Boolean(string='Đang dừng', readonly=True)
    outage_id = fields.Many2one(
        'eam.outage', string='Khoảng dừng', readonly=True,
        ondelete='set null')
    ghi_chu = fields.Char(string='Loại thời gian', readonly=True)
