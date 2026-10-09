# -*- coding: utf-8 -*-
import logging

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class EamPmSchedule(models.Model):
    """Đồng hồ bảo trì của MỘT kế hoạch tại MỘT vị trí.

    Đây là bản ghi cron quét hằng ngày. Nó giữ hai thứ không suy ra được
    từ đâu khác: **lần làm xong gần nhất** và **số đồng hồ tại lần đó**.
    Mất hai số này là mất toàn bộ lịch sử bảo trì — nên khi một vị trí
    ra khỏi phạm vi kế hoạch, bản ghi được cho NGHỈ chứ không xoá.
    """
    _name = 'eam.pm.schedule'
    _description = 'Lịch bảo trì theo vị trí'
    _inherit = ['mail.thread']
    _order = 'date_next, id'
    _rec_name = 'display_name'

    plan_id = fields.Many2one(
        'eam.pm.plan', string='Kế hoạch', required=True, ondelete='cascade',
        index=True)
    location_id = fields.Many2one(
        'eam.location', string='Vị trí', required=True, ondelete='cascade',
        index=True)
    location_code = fields.Char(
        related='location_id.complete_code', store=True, string='Mã vị trí')
    active = fields.Boolean(default=True)

    date_last_done = fields.Date(string='Làm xong lần gần nhất',
                                 tracking=True)
    meter_at_last = fields.Float(
        string='Số đồng hồ lần gần nhất', digits=(16, 2), tracking=True)
    date_start = fields.Date(
        string='Mốc bắt đầu tính',
        help='Dùng khi chưa từng bảo trì lần nào — thường là ngày đưa '
             'vào vận hành. Để trống thì lấy ngày lắp đặt thiết bị.')

    date_next = fields.Date(
        string='Hạn theo lịch', compute='_compute_han', store=True,
        tracking=True)
    meter_next = fields.Float(
        string='Hạn theo đồng hồ', compute='_compute_han', store=True,
        digits=(16, 2))
    meter_now = fields.Float(
        string='Đồng hồ hiện tại', compute='_compute_han', store=True,
        digits=(16, 2))
    days_to_due = fields.Integer(
        string='Còn (ngày)', compute='_compute_han', store=True,
        aggregator=False)
    meter_to_due = fields.Float(
        string='Còn (đơn vị đồng hồ)', compute='_compute_han', store=True,
        digits=(16, 2), aggregator=False)
    due_by = fields.Selection(
        [('calendar', 'Theo lịch'), ('meter', 'Theo đồng hồ'),
         ('none', 'Chưa đủ dữ liệu')],
        string='Tới hạn vì', compute='_compute_han', store=True,
        help='Hai điều kiện thì cái nào ĐẾN TRƯỚC thắng. Cột này nói rõ '
             'cái nào đang quyết định, để khỏi phải đoán.')
    state = fields.Selection(
        [('ok', 'Còn hạn'),
         ('due_soon', 'Sắp tới hạn'),
         ('overdue', 'QUÁ HẠN'),
         ('wo_open', 'Đã có lệnh'),
         ('no_data', 'Thiếu số đọc đồng hồ')],
        string='Tình trạng', compute='_compute_han', store=True, index=True)

    wo_id = fields.Many2one(
        'eam.work.order', string='Lệnh đang mở', copy=False, tracking=True)
    wo_ids = fields.One2many(
        'eam.work.order', 'pm_schedule_id', string='Lịch sử lệnh')
    wo_count = fields.Integer(string='Số lần đã làm',
                              compute='_compute_wo_count')
    company_id = fields.Many2one(
        related='location_id.company_id', store=True, index=True)

    _uniq = models.Constraint(
        'UNIQUE(plan_id, location_id)',
        'Mỗi kế hoạch chỉ có một lịch cho mỗi vị trí.')

    @api.depends('wo_ids.state')
    def _compute_wo_count(self):
        for s in self:
            s.wo_count = len(s.wo_ids.filtered(
                lambda w: w.state in ('done', 'closed')))

    @api.depends('plan_id', 'date_last_done', 'meter_at_last', 'date_start',
                 'plan_id.use_calendar', 'plan_id.calendar_months',
                 'plan_id.calendar_days', 'plan_id.anchor',
                 'plan_id.use_meter', 'plan_id.meter_interval',
                 'plan_id.meter_type', 'plan_id.lead_days',
                 'wo_id.state')
    def _compute_han(self):
        hn = fields.Date.context_today(self)
        M = self.env['eam.meter']
        for s in self:
            p = s.plan_id
            goc = s.date_last_done or s.date_start or s._mo_goc()

            # ── Hạn theo lịch
            s.date_next = False
            if p.use_calendar and goc:
                if p.anchor == 'fixed_calendar' and not s.date_last_done:
                    s.date_next = goc
                else:
                    s.date_next = goc + relativedelta(
                        months=p.calendar_months or 0,
                        days=p.calendar_days or 0)
                    # Mốc cố định: hạn KHÔNG trôi theo ngày làm thật, nó
                    # nhảy từng bước chu kỳ cho tới khi vượt hôm nay.
                    if p.anchor == 'fixed_calendar':
                        base = s.date_start or goc
                        d = base
                        while d <= hn:
                            d = d + relativedelta(
                                months=p.calendar_months or 0,
                                days=p.calendar_days or 0)
                        s.date_next = d

            # ── Hạn theo đồng hồ
            s.meter_now = s.meter_next = 0.0
            s.meter_to_due = 0.0
            thieu_dh = False
            if p.use_meter:
                dh = M.search([('location_id', '=', s.location_id.id),
                               ('meter_type', '=', p.meter_type)], limit=1)
                if dh and dh.date_last_reading:
                    s.meter_now = dh.current_value
                    s.meter_next = (s.meter_at_last or 0.0) + p.meter_interval
                    s.meter_to_due = s.meter_next - s.meter_now
                else:
                    thieu_dh = True

            s.days_to_due = ((s.date_next - hn).days if s.date_next else 0)

            # ── Cái nào ĐẾN TRƯỚC thắng.
            #
            # Hai điều kiện đo bằng hai đơn vị khác nhau, không trừ trực
            # tiếp được. So bằng PHẦN CÒN LẠI CỦA CHU KỲ: còn 10% chu kỳ
            # lịch thì gần hơn còn 40% chu kỳ đồng hồ, dù một bên là
            # ngày một bên là giờ.
            ck_ngay = ((p.calendar_months or 0) * 30
                       + (p.calendar_days or 0)) or 1
            ti_lich = (s.days_to_due / float(ck_ngay)
                       if p.use_calendar and s.date_next else None)
            ti_dh = (s.meter_to_due / p.meter_interval
                     if p.use_meter and not thieu_dh and p.meter_interval
                     else None)
            if ti_lich is None and ti_dh is None:
                s.due_by = 'none'
            elif ti_dh is None:
                s.due_by = 'calendar'
            elif ti_lich is None:
                s.due_by = 'meter'
            else:
                s.due_by = 'meter' if ti_dh <= ti_lich else 'calendar'

            den_lich = bool(s.date_next) and p.use_calendar \
                and s.days_to_due <= p.lead_days
            den_dh = p.use_meter and not thieu_dh and s.meter_to_due <= 0

            # ── Tình trạng
            if s.wo_id and s.wo_id.state not in ('done', 'closed',
                                                 'cancelled'):
                s.state = 'wo_open'
            elif p.use_meter and thieu_dh and not p.use_calendar:
                # Chỉ chạy theo đồng hồ mà không có số đọc thì kế hoạch
                # này IM LẶNG không bao giờ tới hạn. Phải nói ra, chứ
                # không để nó nằm đó mãi ở trạng thái "còn hạn".
                s.state = 'no_data'
            elif (p.use_calendar and s.date_next and s.days_to_due < 0) \
                    or (den_dh and s.meter_to_due < 0):
                s.state = 'overdue'
            elif den_lich or den_dh:
                s.state = 'due_soon'
            else:
                s.state = 'ok'

    def _mo_goc(self):
        """Chưa từng bảo trì thì tính từ ngày lắp thiết bị."""
        self.ensure_one()
        I = self.env['eam.installation'].search(
            [('location_id', 'child_of', self.location_id.id)],
            order='date_install', limit=1)
        return I.date_install or False

    @api.depends('plan_id', 'location_code')
    def _compute_display_name(self):
        for s in self:
            s.display_name = '%s · %s' % (s.location_code or '?',
                                          s.plan_id.name or '?')

    # ------------------------------------------------------------------
    def _sinh_lenh(self):
        """Tạo lệnh công việc từ kế hoạch. Trả về lệnh vừa tạo."""
        self.ensure_one()
        p = self.plan_id
        W = self.env['eam.work.order']
        buoc = '\n'.join(
            '%d. %s%s' % (i + 1, t.name,
                          ' — %s' % t.spec if t.spec else '')
            for i, t in enumerate(p.task_ids.sorted('sequence')))
        mo = p.note or ''
        if buoc:
            mo = (mo + '\n\n' if mo else '') + 'CÁC BƯỚC:\n' + buoc
        w = W.create({
            'title': '%s — %s' % (p.name, self.location_id.code or ''),
            'work_type': p.work_type,
            'priority': p.priority,
            'location_id': self.location_id.id,
            'date_planned_start': self.date_next or
            fields.Date.context_today(self),
            'date_planned_end': self.date_next or
            fields.Date.context_today(self),
            'requires_permit': p.requires_permit,
            'requires_isolation': p.requires_isolation,
            'work_at_height': p.work_at_height,
            'description': mo,
            'pm_plan_id': p.id,
            'pm_schedule_id': self.id,
        })
        self.wo_id = w.id
        return w

    def action_sinh_lenh_ngay(self):
        for s in self:
            if s.wo_id and s.wo_id.state not in ('done', 'closed',
                                                 'cancelled'):
                raise UserError(_(
                    '%s đã có lệnh đang mở (%s). Sinh thêm là có hai lệnh '
                    'cùng một việc, và lần nào làm xong cũng không biết '
                    'nên đóng cái nào.', s.display_name, s.wo_id.name))
            s._sinh_lenh()
        return True

    def action_ghi_da_lam(self):
        """Ghi nhận đã bảo trì xong mà không qua lệnh công việc."""
        for s in self:
            s._dong_ho_chay_tiep(fields.Date.context_today(s))
        return True

    def _dong_ho_chay_tiep(self, ngay):
        """Chốt lần làm xong — đây là chỗ chu kỳ tiếp theo bắt đầu đếm."""
        self.ensure_one()
        M = self.env['eam.meter']
        v = {'date_last_done': ngay}
        if self.plan_id.use_meter:
            dh = M.search([('location_id', '=', self.location_id.id),
                           ('meter_type', '=', self.plan_id.meter_type)],
                          limit=1)
            if dh:
                v['meter_at_last'] = dh.current_value
        self.write(v)

    # ------------------------------------------------------------------
    @api.model
    def _cron_sinh_lenh(self):
        """Quét lịch, sinh lệnh cho những cái sắp tới hạn.

        Hai chốt chặn:

        * chỉ sinh khi **chưa có lệnh đang mở** — cron chạy hằng ngày mà
          kế hoạch quá hạn thì ngày nào cũng thoả điều kiện, không chặn
          thì sau một tháng có 30 lệnh y hệt nhau cho cùng một máy;
        * các lệnh sinh cùng một lượt của cùng một kế hoạch được gom về
          **một lệnh chiến dịch cha**, để 12 tua-bin cùng tới kỳ bảo
          dưỡng hiện ra là một đợt chứ không phải 12 việc rời rạc.
        """
        ds = self.search([('state', 'in', ('due_soon', 'overdue'))])
        ds = ds.filtered(lambda s: not (
            s.wo_id and s.wo_id.state not in ('done', 'closed', 'cancelled')))
        if not ds:
            return True
        W = self.env['eam.work.order']
        # Gom theo kế hoạch. KHÔNG dùng `|=` trên recordset trong dict:
        # phép hợp trả về recordset MỚI chứ không sửa tại chỗ, nên giá
        # trị trong dict đứng nguyên rỗng và chiến dịch không bao giờ
        # được gom.
        theo_kh = {}
        for s in ds:
            theo_kh.setdefault(s.plan_id.id, []).append(s.id)
        n = 0
        for pid, sids in theo_kh.items():
            p = self.env['eam.pm.plan'].browse(pid)
            nhom = self.browse(sids)
            cha = False
            if len(nhom) > 1:
                cha = W.create({
                    'title': _('Chiến dịch: %s', p.name),
                    'work_type': p.work_type, 'priority': p.priority,
                    'location_id': nhom[0].location_id.id,
                    'pm_plan_id': p.id,
                    'description': _('Gom %d vị trí cùng tới kỳ.', len(nhom)),
                }).id
            for s in nhom:
                w = s._sinh_lenh()
                if cha:
                    w.parent_id = cha
                n += 1
        _logger.info('eam_pm: đã sinh %d lệnh bảo trì phòng ngừa.', n)
        return True
