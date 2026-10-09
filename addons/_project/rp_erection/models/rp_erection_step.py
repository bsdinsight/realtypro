# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class RpErectionStep(models.Model):
    """Một vị trí × một cổng — ô của sổ dựng máy.

    Ba quyết định, cả ba đều ngược trực giác
    ----------------------------------------

    **① KHÔNG chặn khi qua cổng sau mà cổng trước chưa xong.** Không thể
    dựng tháp trước khi đổ móng — nhưng chuyện đó xảy ra TRÊN SỔ suốt,
    vì người ghi quên tích cổng móng chứ không phải vì họ dựng tháp lên
    bùn. Chặn thì họ sẽ tích bừa cổng trước cho qua, và mất sạch dấu vết.
    Thay vào đó đánh dấu ``out_of_order`` và đưa ra màn hình để người có
    thẩm quyền soi.

    **② "Đang kẹt" là một trạng thái riêng, không phải "chưa làm".** Một
    trụ chưa tới lượt và một trụ dừng vì chờ cẩu trông giống hệt nhau
    nếu chỉ có xong/chưa xong. Mà đó đúng là câu quản lý mở màn hình này
    để hỏi.

    **③ Trễ đo theo NGÀY KẾ HOẠCH của chính ô đó**, không theo mốc hạng
    mục. Hạng mục "móng 30 vị trí" xong đúng hạn vẫn có thể che một trụ
    trễ 40 ngày bị bù bằng 29 trụ xong sớm.
    """
    _name = 'rp.erection.step'
    _description = 'Bước dựng máy tại một vị trí'
    _inherit = ['mail.thread']
    _order = 'location_code, gate_sequence'
    _rec_name = 'display_name'

    location_id = fields.Many2one(
        'eam.location', string='Vị trí', required=True, ondelete='cascade',
        index=True, domain="[('location_type', '=', 'position')]")
    location_code = fields.Char(
        related='location_id.code', store=True, string='Mã vị trí')
    gate_id = fields.Many2one(
        'rp.erection.gate', string='Cổng', required=True,
        ondelete='cascade', index=True)
    gate_sequence = fields.Integer(
        related='gate_id.sequence', store=True, string='Thứ tự cổng')
    structure_id = fields.Many2one(
        related='gate_id.structure_id', store=True, string='Hạng mục')

    state = fields.Selection(
        [('pending', 'Chưa tới lượt'),
         ('in_progress', 'Đang làm'),
         ('blocked', 'Đang kẹt'),
         ('done', 'Đã xong')],
        string='Trạng thái', default='pending', required=True,
        tracking=True, index=True)
    blocked_reason = fields.Selection(
        [('weather', 'Thời tiết'),
         ('crane', 'Chờ cẩu'),
         ('material', 'Chờ vật tư, thiết bị'),
         ('design', 'Chờ bản vẽ, trình duyệt'),
         ('access', 'Chờ đường vào, mặt bằng'),
         ('manpower', 'Thiếu nhân lực'),
         ('inspection', 'Chờ nghiệm thu'),
         ('grid', 'Chờ điện lực'),
         ('other', 'Lý do khác')],
        string='Kẹt vì', tracking=True)
    blocked_note = fields.Char(string='Diễn giải kẹt')

    date_plan = fields.Date(string='Kế hoạch xong', tracking=True)
    date_done = fields.Date(string='Thực tế xong', tracking=True, copy=False)
    days_late = fields.Integer(
        string='Trễ (ngày)', compute='_compute_late', store=True,
        aggregator=False,
        help='Đã xong thì đo tới ngày xong; chưa xong thì đo tới HÔM NAY '
             '— để con số không đứng im và trông như vẫn còn hạn.')
    out_of_order = fields.Boolean(
        string='Qua cổng sau khi cổng trước chưa xong',
        compute='_compute_out_of_order', store=True,
        help='KHÔNG chặn, vì phần lớn là do người ghi quên tích cổng '
             'trước chứ không phải dựng tháp lên bùn. Chặn thì họ tích '
             'bừa cho qua và mất sạch dấu vết.')
    note = fields.Text(string='Ghi chú')
    company_id = fields.Many2one(
        related='location_id.company_id', store=True, index=True)

    _uniq = models.Constraint(
        'UNIQUE(location_id, gate_id)',
        'Mỗi vị trí chỉ có một dòng cho mỗi cổng.')

    @api.depends('date_plan', 'date_done', 'state')
    def _compute_late(self):
        hn = fields.Date.context_today(self)
        for s in self:
            if not s.date_plan:
                s.days_late = 0
                continue
            moc = s.date_done if s.state == 'done' else hn
            s.days_late = max((moc - s.date_plan).days, 0)

    @api.depends('state', 'gate_sequence', 'location_id')
    def _compute_out_of_order(self):
        for s in self:
            if s.state != 'done' or not s.location_id:
                s.out_of_order = False
                continue
            truoc = self.search([
                ('location_id', '=', s.location_id.id),
                ('gate_sequence', '<', s.gate_sequence),
                ('state', '!=', 'done')])
            s.out_of_order = bool(truoc)

    @api.constrains('state', 'blocked_reason')
    def _check_ly_do_ket(self):
        for s in self:
            if s.state == 'blocked' and not s.blocked_reason:
                raise ValidationError(_(
                    '%s đang kẹt mà không ghi kẹt vì gì. Ô này là chỗ '
                    'duy nhất phân biệt được "chưa tới lượt" với "dừng '
                    'vì chờ cẩu" — bỏ trống thì mọi trụ chậm trông giống '
                    'nhau.', s.display_name))

    @api.depends('location_code', 'gate_id')
    def _compute_display_name(self):
        for s in self:
            s.display_name = '%s · %s' % (s.location_code or '?',
                                          s.gate_id.name or '?')

    # ------------------------------------------------------------------
    def action_xong(self):
        for s in self:
            s.write({'state': 'done',
                     'date_done': s.date_done or fields.Date.context_today(s),
                     'blocked_reason': False, 'blocked_note': False})
        return True

    def action_bat_dau(self):
        self.write({'state': 'in_progress', 'blocked_reason': False,
                    'blocked_note': False})
        return True

    def write(self, vals):
        r = super().write(vals)
        # Xong một cổng thì cờ "qua cổng sau khi cổng trước chưa xong"
        # của CÁC CỔNG SAU ở cùng vị trí phải tính lại — @api.depends
        # chỉ theo dõi trường của chính bản ghi, nên không tự biết.
        if 'state' in vals:
            sau = self.search([
                ('location_id', 'in', self.mapped('location_id').ids),
                ('state', '=', 'done')])
            sau._compute_out_of_order()
            sau.flush_recordset(['out_of_order'])
        return r
