# -*- coding: utf-8 -*-
"""Sổ cảnh báo — và cây cầu từ cảnh báo sang lệnh công việc.

Một cảnh báo là một ĐỢT, không phải một lần nổ
----------------------------------------------
Đầu đo rung vượt ngưỡng thì cron hằng ngày sẽ thấy nó vượt mỗi ngày.
Ghi một bản ghi mỗi ngày là sau một tháng có 30 cảnh báo y hệt nhau cho
cùng một trụ — đúng cái bẫy mà kế hoạch bảo trì phòng ngừa đã phải
chặn. Nên một bản ghi ở đây là **một đợt**: từ lúc điều kiện thành đúng
tới lúc nó hết. Nổ lại trong đợt chỉ cộng ``occurrence_count``.

Và chính con số đó lại là thông tin: *"cảnh báo này đã nổ 47 lần"* nói
khác hẳn *"cảnh báo này vừa nổ"*, dù hai dòng trông giống nhau.

``repeat_after_fix`` — con số đắt nhất trong sổ này
---------------------------------------------------
Cảnh báo tắt vì đã đóng lệnh sửa, rồi quay lại sau hai tuần. Nghĩa là
**lần sửa đó không giữ được**: hoặc sửa sai chỗ, hoặc chỉ xử lý triệu
chứng, hoặc phụ tùng thay vào là phụ tùng kém. Không hệ nào theo dõi
con số này, và mọi đội bảo trì đều cần nó — vì nó là cách duy nhất phân
biệt "đã sửa" với "đã đóng lệnh".

Đợt tái phát còn được **nâng một mức nghiêm trọng** so với luật. Thứ
quay lại sau khi đã sửa thì nguy hơn lần đầu, không phải bằng.

Vì sao "bỏ qua" phải khai lý do
-------------------------------
Bỏ qua là quyết định có hậu quả — và là lối thoát mà ai cũng dùng khi
cảnh báo nhiều quá. Không bắt khai lý do thì sau sáu tháng sổ này đầy
dòng "đã bỏ qua" mà không ai nhớ vì sao, kể cả người bỏ qua.
"""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from odoo.addons.eam_alarm.models.eam_alarm_rule import (
    MUC, NGUON, THU_TU_MUC,
)

_logger = logging.getLogger(__name__)

TRANG_THAI = [
    ('new', 'Mới'),
    ('ack', 'Đã xác nhận'),
    ('wo', 'Đã có lệnh'),
    ('cleared', 'Đã hết'),
    ('ignored', 'Đã bỏ qua'),
]
DANG_MO = ('new', 'ack', 'wo')


class EamAlarm(models.Model):
    _name = 'eam.alarm'
    _description = 'Cảnh báo thiết bị'
    _inherit = ['mail.thread']
    _order = 'date_raised desc, id desc'
    _rec_name = 'display_name'

    rule_id = fields.Many2one(
        'eam.alarm.rule', string='Luật', ondelete='restrict', index=True,
        help='Để trống khi người trực tự báo — không phải cảnh báo nào '
             'cũng từ máy.')
    source = fields.Selection(
        NGUON, string='Nguồn', required=True, default='manual', index=True)
    location_id = fields.Many2one(
        'eam.location', string='Vị trí', required=True, ondelete='restrict',
        index=True, tracking=True)
    asset_id = fields.Many2one(
        'eam.asset', string='Thiết bị', compute='_compute_asset', store=True,
        readonly=False, index=True,
        help='Suy từ vị trí: thiết bị đang lắp ở đó. Sửa được khi cảnh báo '
             'chỉ đích danh một cấu phần bên trong.')
    message = fields.Char(string='Nội dung', required=True, tracking=True)
    severity = fields.Selection(
        MUC, string='Mức nghiêm trọng', required=True, default='medium',
        index=True, tracking=True)
    value_seen = fields.Float(
        string='Trị số lúc nổ', digits=(16, 4),
        help='Giữ lại số ĐO ĐƯỢC, không chỉ giữ câu chữ. Không có nó thì '
             'sau này không đối chiếu lại được là cảnh báo nổ vì vượt bao '
             'nhiêu.')

    state = fields.Selection(
        TRANG_THAI, string='Trạng thái', required=True, default='new',
        index=True, tracking=True, copy=False)
    date_raised = fields.Datetime(
        string='Nổ lúc', required=True, default=fields.Datetime.now,
        index=True, tracking=True)
    date_last_seen = fields.Datetime(
        string='Thấy lần cuối', default=fields.Datetime.now)
    date_cleared = fields.Datetime(string='Hết lúc', copy=False,
                                   tracking=True)
    occurrence_count = fields.Integer(
        string='Số lần nổ', default=1, copy=False,
        help='Nổ lại khi đợt còn mở chỉ cộng vào đây, không sinh dòng mới. '
             'Nổ 47 lần khác hẳn vừa nổ, dù hai dòng trông giống nhau.')

    # ------------------------------------------------------------------
    # Lệnh công việc
    # ------------------------------------------------------------------
    wo_id = fields.Many2one(
        'eam.work.order', string='Lệnh công việc', copy=False, index=True,
        tracking=True, ondelete='set null')
    wo_state = fields.Selection(
        related='wo_id.state', string='Trạng thái lệnh')

    ack_user_id = fields.Many2one('res.users', string='Người xác nhận',
                                  readonly=True, copy=False)
    ack_date = fields.Datetime(string='Xác nhận lúc', readonly=True,
                               copy=False)
    ignore_reason = fields.Char(string='Lý do bỏ qua', tracking=True,
                                copy=False)

    # ------------------------------------------------------------------
    # Tái phát
    # ------------------------------------------------------------------
    prev_id = fields.Many2one(
        'eam.alarm', string='Đợt trước', ondelete='set null', copy=False,
        help='Đợt cảnh báo cùng luật, cùng vị trí ngay trước đợt này.')
    repeat_after_fix = fields.Integer(
        string='Số lần tái phát sau sửa', default=0, copy=False, index=True,
        tracking=True,
        help='Đếm số lần cảnh báo QUAY LẠI sau khi đã đóng lệnh sửa. Lớn '
             'hơn 0 là lần sửa trước không giữ được — đây là cách duy nhất '
             'phân biệt "đã sửa" với "đã đóng lệnh".')
    is_repeat = fields.Boolean(
        string='Là tái phát', compute='_compute_is_repeat', store=True)

    company_id = fields.Many2one(
        related='location_id.company_id', store=True, index=True)

    # ------------------------------------------------------------------
    @api.depends('location_id', 'date_raised')
    def _compute_asset(self):
        I = self.env['eam.installation']
        for a in self:
            if not a.location_id:
                a.asset_id = False
                continue
            ngay = (a.date_raised or fields.Datetime.now()).date()
            lap = I.search(
                [('location_id', '=', a.location_id.id),
                 ('date_install', '<=', ngay),
                 '|', ('date_remove', '=', False),
                 ('date_remove', '>=', ngay)], limit=1)
            a.asset_id = lap.asset_id.id if lap else False

    @api.depends('repeat_after_fix')
    def _compute_is_repeat(self):
        for a in self:
            a.is_repeat = a.repeat_after_fix > 0

    @api.depends('location_id', 'message', 'severity')
    def _compute_display_name(self):
        nhan = dict(self._fields['severity'].selection)
        for a in self:
            a.display_name = '%s · %s — %s' % (
                a.location_id.complete_code or '?',
                nhan.get(a.severity, ''), (a.message or '')[:60])

    @api.constrains('state', 'ignore_reason')
    def _check_ly_do_bo_qua(self):
        for a in self:
            if a.state == 'ignored' and not a.ignore_reason:
                raise ValidationError(_(
                    'Bỏ qua cảnh báo "%s" thì phải ghi lý do. Không ghi thì '
                    'sau sáu tháng sổ cảnh báo đầy dòng "đã bỏ qua" mà '
                    'không ai nhớ vì sao, kể cả người bỏ qua.',
                    a.message or ''))

    # ------------------------------------------------------------------
    # Ghi nhận — chỗ chống rác
    # ------------------------------------------------------------------
    @api.model
    def _ghi_nhan(self, rule, location, message, value=None, severity=None,
                  source=None):
        """Ghi một cảnh báo, gộp vào đợt đang mở nếu có.

        Đây là cửa duy nhất nên đi vào khi tạo cảnh báo tự động — gọi
        ``create()`` trực tiếp là bỏ qua toàn bộ phần chống trùng.
        """
        dang_mo = self.search(
            [('rule_id', '=', rule.id if rule else False),
             ('location_id', '=', location.id),
             ('state', 'in', list(DANG_MO))], limit=1)
        gio = fields.Datetime.now()
        if dang_mo:
            dang_mo.write({
                'occurrence_count': dang_mo.occurrence_count + 1,
                'date_last_seen': gio,
                'value_seen': value if value is not None
                else dang_mo.value_seen,
            })
            return dang_mo

        # Đợt mới. Có phải TÁI PHÁT sau sửa không?
        truoc = self.search(
            [('rule_id', '=', rule.id if rule else False),
             ('location_id', '=', location.id),
             ('state', '=', 'cleared')],
            order='date_cleared desc, id desc', limit=1)
        lap = 0
        cua_so = (rule.repeat_window_days if rule else 30) or 30
        if truoc and truoc.date_cleared and truoc.wo_id \
                and truoc.wo_id.state in ('done', 'closed'):
            cach = (gio - truoc.date_cleared).days
            # Im lặng đủ lâu rồi mới nổ lại thì là đợt mới, không phải
            # lần sửa trước thất bại. Đếm bừa vào tái phát là thổi phồng
            # con số đáng tin nhất của sổ này.
            lap = (truoc.repeat_after_fix + 1) if cach <= cua_so else 0

        muc = severity or (rule.severity if rule else 'medium')
        if lap:
            # Quay lại sau khi đã sửa thì nguy hơn lần đầu, không phải bằng.
            thang = sorted(THU_TU_MUC, key=lambda k: THU_TU_MUC[k])
            muc = thang[min(THU_TU_MUC[muc] + 1, len(thang) - 1)]

        a = self.create({
            'rule_id': rule.id if rule else False,
            'source': source or (rule.source if rule else 'manual'),
            'location_id': location.id,
            'message': message or _('Cảnh báo không có nội dung'),
            'severity': muc,
            'value_seen': value or 0.0,
            'date_raised': gio,
            'date_last_seen': gio,
            'prev_id': truoc.id if truoc else False,
            'repeat_after_fix': lap,
        })
        if lap:
            a.message_post(body=_(
                'Cảnh báo này đã TÁI PHÁT lần thứ %(n)d sau khi đóng lệnh '
                '%(l)s ngày %(d)s. Lần sửa đó không giữ được — xem lại '
                'nguyên nhân gốc thay vì sửa lại y như cũ.',
                n=lap, l=truoc.wo_id.name or '',
                d=truoc.date_cleared and truoc.date_cleared.date() or ''))
        if rule and rule.auto_wo == 'immediate':
            a._tao_lenh()
        return a

    @api.model
    def _tu_tat(self, rule, location):
        """Điều kiện đã hết: tắt đợt đang mở. Trả về số đợt đã tắt."""
        ds = self.search([('rule_id', '=', rule.id),
                          ('location_id', '=', location.id),
                          ('state', 'in', ('new', 'ack'))])
        # Đợt đã có lệnh thì KHÔNG tự tắt: trị số về bình thường trong lúc
        # chờ sửa là chuyện thường (máy được cho dừng), tắt đi là lệnh mồ
        # côi không ai biết mở ra vì sao.
        if not ds:
            return 0
        ds.write({'state': 'cleared',
                  'date_cleared': fields.Datetime.now()})
        return len(ds)

    # ------------------------------------------------------------------
    def _tao_lenh(self):
        """Mở lệnh công việc từ cảnh báo. Gộp vào lệnh đang mở nếu có."""
        self.ensure_one()
        if self.wo_id and self.wo_id.state not in ('done', 'closed',
                                                   'cancelled'):
            return self.wo_id
        W = self.env['eam.work.order']
        r = self.rule_id

        # Hai cảnh báo khác luật nhưng cùng một trụ, cùng một ngày thì
        # vẫn nên ra MỘT lần đi hiện trường. Gộp vào lệnh đang mở của
        # cùng vị trí do cảnh báo sinh ra.
        cung_cho = self.search(
            [('location_id', '=', self.location_id.id),
             ('id', '!=', self.id),
             ('wo_id', '!=', False),
             ('wo_id.state', 'in', ('draft', 'approved', 'planned',
                                    'in_progress'))], limit=1)
        if cung_cho:
            w = cung_cho.wo_id
            self.write({'wo_id': w.id, 'state': 'wo'})
            w.message_post(body=_(
                'Gộp thêm cảnh báo: %s', self.message))
            return w

        buoc = []
        if r and r.pm_plan_id:
            buoc = [(0, 0, {
                'sequence': t.sequence, 'name': t.name, 'spec': t.spec,
                'is_critical': t.is_critical, 'pm_task_id': t.id,
            }) for t in r.pm_plan_id.task_ids.sorted('sequence')]

        mo_ta = [_('Mở từ cảnh báo: %s', self.message)]
        if self.occurrence_count > 1:
            mo_ta.append(_('Đã nổ %d lần.', self.occurrence_count))
        if self.repeat_after_fix:
            mo_ta.append(_(
                'TÁI PHÁT lần thứ %d sau sửa — đừng sửa lại y như lần '
                'trước, hãy xem lại nguyên nhân gốc.', self.repeat_after_fix))
        if r and r.note:
            mo_ta.append(r.note)

        w = W.create({
            'title': (r.name if r else _('Cảnh báo')) + ' — '
            + (self.location_id.code or ''),
            'work_type': r.wo_work_type if r else 'inspection',
            'priority': r.wo_priority if r else '2',
            'location_id': self.location_id.id,
            'asset_id': self.asset_id.id or False,
            'date_planned_start': fields.Datetime.now(),
            'detection_method': r.wo_detection if r else 'operator',
            'requires_permit': r.wo_requires_permit if r else False,
            'requires_isolation': r.wo_requires_isolation if r else False,
            'work_at_height': r.wo_work_at_height if r else False,
            'description': '\n'.join(mo_ta),
            'step_ids': buoc,
        })
        self.write({'wo_id': w.id, 'state': 'wo'})
        w.message_post(body=_(
            'Lệnh này do cảnh báo %(m)s sinh ra.', m=self.display_name))
        return w

    # ------------------------------------------------------------------
    def action_xac_nhan(self):
        for a in self:
            if a.state != 'new':
                raise UserError(_(
                    'Cảnh báo "%s" không còn ở trạng thái mới.', a.message))
            a.write({'state': 'ack', 'ack_user_id': self.env.uid,
                     'ack_date': fields.Datetime.now()})
            if a.rule_id and a.rule_id.auto_wo == 'on_ack':
                a._tao_lenh()
        return True

    def action_tao_lenh(self):
        for a in self:
            if a.state not in ('new', 'ack'):
                raise UserError(_(
                    'Cảnh báo "%s" đã có lệnh hoặc đã khép.', a.message))
            if not a.ack_user_id:
                a.write({'ack_user_id': self.env.uid,
                         'ack_date': fields.Datetime.now()})
            a._tao_lenh()
        return True

    def action_mo_lenh(self):
        self.ensure_one()
        if not self.wo_id:
            raise UserError(_('Cảnh báo này chưa có lệnh công việc.'))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'eam.work.order',
            'view_mode': 'form',
            'res_id': self.wo_id.id,
        }

    def action_bo_qua(self):
        """Mở hộp thoại khai lý do — không bỏ qua được mà không nói vì sao."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Bỏ qua cảnh báo'),
            'res_model': 'eam.alarm.ignore.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_alarm_ids': self.ids},
        }

    def action_het(self):
        for a in self:
            if a.state not in DANG_MO:
                raise UserError(_('Cảnh báo "%s" đã khép.', a.message))
            a.write({'state': 'cleared',
                     'date_cleared': fields.Datetime.now()})
        return True

    def action_mo_lai(self):
        for a in self:
            a.write({'state': 'new', 'date_cleared': False,
                     'ignore_reason': False})
        return True


class EamAlarmIgnoreWizard(models.TransientModel):
    """Hộp thoại khai lý do bỏ qua.

    Wizard tạm PHẢI có quyền truy cập khai trong ``ir.model.access`` —
    kể cả admin cũng bị quyền chặn, và lỗi hiện ra là "không có quyền"
    chứ không nói gì về việc thiếu khai báo.
    """
    _name = 'eam.alarm.ignore.wizard'
    _description = 'Bỏ qua cảnh báo'

    alarm_ids = fields.Many2many('eam.alarm', string='Cảnh báo',
                                 required=True)
    reason = fields.Char(string='Lý do bỏ qua', required=True)

    def action_xac_nhan(self):
        self.ensure_one()
        self.alarm_ids.write({
            'state': 'ignored', 'ignore_reason': self.reason,
            'date_cleared': fields.Datetime.now()})
        for a in self.alarm_ids:
            a.message_post(body=_('Bỏ qua. Lý do: %s', self.reason))
        return {'type': 'ir.actions.act_window_close'}
