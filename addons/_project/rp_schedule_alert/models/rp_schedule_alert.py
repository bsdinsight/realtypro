# -*- coding: utf-8 -*-
"""Cảnh báo trượt tiến độ — phát hiện sớm, có lịch sử, không spam.

Lịch thi công và sổ giao diện đã có đủ số để biết dự án đang hỏng ở đâu,
nhưng chỉ khi có người MỞ RA XEM. Thực tế thì không ai ngồi soi 485 công
việc mỗi sáng, nên chuyện trượt lộ ra lúc đã muộn.

Ở đây mỗi lần quét sinh ra bản ghi cảnh báo theo bốn ngưỡng (dự án trễ
mốc, việc hết dư địa, việc trượt so kế hoạch gốc, điểm giao mâu thuẫn).
Ba điều quyết định việc này dùng được hay không:

* **Không nhân bản**: cảnh báo đang mở của cùng một đối tượng thì cập
  nhật con số và ngày thấy lần cuối, không tạo thêm. Nhờ vậy mới trả lời
  được "chuyện này cảnh báo từ bao giờ" — bằng chứng cho hồ sơ khiếu nại.
* **Tự đóng**: điều kiện hết thì cảnh báo chuyển sang đã xử lý, ghi rõ
  ngày. Danh sách luôn là tình trạng HIỆN TẠI, không phải bãi rác.
* **Một bản tin mỗi lần quét**: ghi một ghi chú tổng hợp vào dự án thay
  vì bắn 54 thông báo. Người ta tắt thông báo khi bị bắn quá nhiều, và
  lúc đó cái cảnh báo thật cũng chết theo.
"""
from odoo import _, api, fields, models

SEVERITY_ORDER = {'info': 0, 'warning': 1, 'critical': 2}
OPEN_STATES = ('open', 'acknowledged')


class RpScheduleAlert(models.Model):
    _name = 'rp.schedule.alert'
    _description = 'Cảnh báo trượt tiến độ'
    _inherit = ['mail.thread']
    _order = 'severity_order desc, days_value, id'

    name = fields.Char(
        string='Cảnh báo', compute='_compute_name', store=True)
    project_id = fields.Many2one(
        're.project', string='Dự án', required=True, index=True,
        ondelete='cascade')
    alert_type = fields.Selection(
        [('project_deadline', 'Dự án trễ mốc phải xong'),
         ('task_float', 'Công việc hết dư địa'),
         ('task_slip', 'Công việc trượt so kế hoạch gốc'),
         ('interface_conflict', 'Điểm giao mâu thuẫn lịch')],
        string='Loại cảnh báo', required=True, index=True)
    severity = fields.Selection(
        [('info', 'Theo dõi'), ('warning', 'Cảnh báo'),
         ('critical', 'Nghiêm trọng')],
        string='Mức độ', default='warning', required=True, index=True,
        tracking=True)
    severity_order = fields.Integer(
        string='Thứ tự mức độ', compute='_compute_severity_order',
        store=True)

    task_id = fields.Many2one(
        'project.task', string='Công việc', index=True, ondelete='cascade')
    interface_id = fields.Many2one(
        'rp.interface', string='Điểm giao', index=True, ondelete='cascade')
    contract_id = fields.Many2one(
        'rp.contract', string='Hợp đồng', index=True, ondelete='cascade')
    partner_id = fields.Many2one(
        'res.partner', string='Nhà thầu',
        related='contract_id.contractor_id', store=True)

    days_value = fields.Integer(
        string='Số ngày', help='Dư địa còn lại (âm là đã trễ) hoặc số '
                               'ngày trượt, tuỳ loại cảnh báo.')
    threshold = fields.Integer(string='Ngưỡng áp dụng')
    description = fields.Char(string='Diễn giải')

    state = fields.Selection(
        [('open', 'Đang mở'),
         ('acknowledged', 'Đã tiếp nhận'),
         ('resolved', 'Đã xử lý'),
         ('ignored', 'Bỏ qua')],
        string='Trạng thái', default='open', required=True, index=True,
        tracking=True)
    date_first = fields.Datetime(
        string='Phát hiện lần đầu', default=fields.Datetime.now,
        readonly=True)
    date_last = fields.Datetime(
        string='Thấy lần cuối', default=fields.Datetime.now, readonly=True)
    date_resolved = fields.Datetime(string='Ngày hết', readonly=True)
    age_days = fields.Integer(
        string='Tồn (ngày)', compute='_compute_age',
        help='Cảnh báo này đã mở bao nhiêu ngày — con số nói lên việc có '
             'ai xử lý hay không.')
    user_id = fields.Many2one(
        'res.users', string='Người theo dõi', tracking=True)

    # ------------------------------------------------------------------
    @api.depends('severity')
    def _compute_severity_order(self):
        for rec in self:
            rec.severity_order = SEVERITY_ORDER.get(rec.severity, 0)

    @api.depends('alert_type', 'task_id', 'interface_id', 'project_id',
                 'days_value')
    def _compute_name(self):
        for rec in self:
            subject = (rec.task_id.name or rec.interface_id.name
                       or rec.project_id.name or '')
            label = dict(self._fields['alert_type'].selection).get(
                rec.alert_type, '')
            rec.name = f'{label}: {subject}' if subject else label

    @api.depends('date_first', 'date_resolved')
    def _compute_age(self):
        now = fields.Datetime.now()
        for rec in self:
            end = rec.date_resolved or now
            rec.age_days = ((end - rec.date_first).days
                            if rec.date_first else 0)

    # ------------------------------------------------------------------
    # Quét
    # ------------------------------------------------------------------
    @api.model
    def _heads_only(self, qualifying, worse_or_equal):
        """Giữ lại ĐẦU CHUỖI, bỏ các việc chỉ thừa hưởng vấn đề.

        Một chuỗi 139 công việc cùng trượt 42 ngày không phải 139 vấn đề
        — nó là MỘT vấn đề ở đầu chuỗi và 138 hệ quả. Báo cả 139 thì
        người nhận tắt thông báo, và cảnh báo thật chết theo.

        Một việc là đầu chuỗi khi không có việc đứng trước nào cũng dính
        cùng loại vấn đề ở mức ngang hoặc tệ hơn.

        Trả (danh sách đầu chuỗi, {id đầu chuỗi: số việc kéo theo}).
        """
        ids = set(qualifying.ids)
        heads = qualifying.filtered(lambda t: not any(
            p.id in ids and worse_or_equal(p, t)
            for p in t.predecessor_ids))
        # Đếm hệ quả: đi xuôi theo successor trong chính tập có vấn đề.
        succ = {i: [] for i in ids}
        for t in qualifying:
            for p in t.predecessor_ids:
                if p.id in ids:
                    succ[p.id].append(t.id)
        downstream = {}
        for h in heads:
            seen, stack = set(), list(succ.get(h.id, []))
            while stack:
                cur = stack.pop()
                if cur in seen:
                    continue
                seen.add(cur)
                stack.extend(succ.get(cur, []))
            downstream[h.id] = len(seen)
        return heads, downstream

    @api.model
    def _candidates(self, project):
        """Trả danh sách cảnh báo ĐÁNG CÓ cho dự án, ở dạng dict.

        Khoá nhận dạng là (loại, công việc, điểm giao) — cùng khoá thì
        là cùng một chuyện, dù con số đã đổi.
        """
        out = []
        today = fields.Date.context_today(self)
        # Tính lại đường găng trước khi quét: cảnh báo mà dựa trên số cũ
        # thì tệ hơn là không có cảnh báo. Kết quả trả về CHỈ gồm việc lá
        # có đủ ngày — dùng luôn làm tập xét, để dòng tổng WBS và việc
        # chưa có ngày không lọt vào (chúng có dư địa 0 theo mặc định,
        # sẽ báo động giả hàng loạt).
        cpm = self.env['project.task'].rp_compute_project_critical_path(
            project.id)

        # 1. Cả dự án trễ mốc phải xong
        slip = project.schedule_deadline_slip
        if project.schedule_deadline and slip > 0:
            out.append({
                'key': ('project_deadline', False, False),
                'alert_type': 'project_deadline',
                'severity': 'critical',
                'days_value': slip,
                'threshold': 0,
                'description': _(
                    'Ngày về đích dự báo %(f)s, muộn hơn mốc phải xong '
                    '%(d)s là %(n)s ngày.',
                    f=project.schedule_forecast_end, d=project.schedule_deadline,
                    n=slip),
            })

        # 2. Công việc hết dư địa trên đường găng toàn dự án
        th_float = project.alert_float_days
        leaves = self.env['project.task'].browse(sorted(cpm))
        low_float = leaves.filtered(
            lambda t: cpm[t.id]['tf'] <= th_float
            and t.planned_end and t.planned_end >= today)
        tasks, pulled = self._heads_only(
            low_float, lambda p, t: cpm[p.id]['tf'] <= cpm[t.id]['tf'])
        for t in tasks:
            out.append({
                'key': ('task_float', t.id, False),
                'alert_type': 'task_float',
                'severity': 'critical' if t.project_float < 0 else 'warning',
                'task_id': t.id,
                'contract_id': t.rp_contract_id.id,
                'days_value': t.project_float,
                'threshold': th_float,
                'description': _(
                    'Dư địa toàn dự án còn %(n)s ngày (ngưỡng %(t)s). '
                    'Kết thúc kế hoạch %(e)s. Kéo theo %(d)s việc phía '
                    'sau cũng hết dư địa.',
                    n=t.project_float, t=th_float, e=t.planned_end,
                    d=pulled.get(t.id, 0)),
                'user_id': t.user_ids[:1].id or False,
            })

        # 3. Công việc trượt so kế hoạch gốc
        th_slip = project.alert_slip_days
        late = leaves.filtered(
            lambda t: t.baseline_slip_days >= th_slip
            and t.progress_percent < 100)
        slipped, inherited = self._heads_only(
            late, lambda p, t: p.baseline_slip_days >= t.baseline_slip_days)
        for t in slipped:
            out.append({
                'key': ('task_slip', t.id, False),
                'alert_type': 'task_slip',
                'severity': ('critical' if t.baseline_slip_days >= th_slip * 3
                             else 'warning'),
                'task_id': t.id,
                'contract_id': t.rp_contract_id.id,
                'days_value': t.baseline_slip_days,
                'threshold': th_slip,
                'description': _(
                    'Kết thúc %(e)s, muộn hơn kế hoạch gốc %(b)s là '
                    '%(n)s ngày. Kéo theo %(d)s việc phía sau trượt theo.',
                    e=t.planned_end, b=t.baseline_end,
                    n=t.baseline_slip_days, d=inherited.get(t.id, 0)),
                'user_id': t.user_ids[:1].id or False,
            })

        # 4. Điểm giao mà bên nhận cần trước khi bên giao kịp
        th_gap = project.alert_interface_days
        ifaces = self.env['rp.interface'].search([
            ('project_id', '=', project.id),
            ('gap_days', '<=', th_gap),
            ('schedule_ready_date', '!=', False),
            ('state', 'not in', ('delivered', 'closed', 'cancelled'))])
        for i in ifaces:
            out.append({
                'key': ('interface_conflict', False, i.id),
                'alert_type': 'interface_conflict',
                'severity': ('critical' if i.criticality == 'critical'
                             else 'warning'),
                'interface_id': i.id,
                'contract_id': i.from_contract_id.id,
                'days_value': i.gap_days,
                'threshold': th_gap,
                'description': _(
                    'Bên nhận cần %(n)s nhưng bên giao sẵn sàng %(r)s — '
                    'lệch %(d)s ngày.',
                    n=i.schedule_need_date, r=i.schedule_ready_date,
                    d=i.gap_days),
                'user_id': i.owner_to_user_id.id or False,
            })
        return out

    @api.model
    def _scan_project(self, project):
        """Đối chiếu cảnh báo đáng có với cảnh báo đang mở.

        Trả (mới, cập nhật, tự đóng).
        """
        wanted = {c['key']: c for c in self._candidates(project)}
        opened = self.search([('project_id', '=', project.id),
                              ('state', 'in', OPEN_STATES)])
        by_key = {
            (a.alert_type, a.task_id.id or False, a.interface_id.id or False): a
            for a in opened
        }
        now = fields.Datetime.now()
        new_vals, updated, resolved = [], self.browse(), self.browse()

        for key, vals in wanted.items():
            existing = by_key.pop(key, None)
            payload = {k: v for k, v in vals.items() if k != 'key'}
            if existing:
                existing.write({
                    'days_value': payload['days_value'],
                    'severity': payload['severity'],
                    'description': payload['description'],
                    'date_last': now,
                })
                updated |= existing
            else:
                payload.update({'project_id': project.id,
                                'date_first': now, 'date_last': now})
                new_vals.append(payload)

        # Còn sót trong by_key = điều kiện đã hết → tự đóng
        for alert in by_key.values():
            alert.write({'state': 'resolved', 'date_resolved': now})
            alert.message_post(body=_(
                'Điều kiện cảnh báo không còn — tự đóng.'))
            resolved |= alert

        created = self.create(new_vals) if new_vals else self.browse()
        self._post_digest(project, created, resolved)
        return created, updated, resolved

    @api.model
    def _post_digest(self, project, created, resolved):
        """Một bản tin cho mỗi lần quét, thay vì bắn từng cảnh báo."""
        if not (created or resolved):
            return
        lines = []
        if created:
            crit = created.filtered(lambda a: a.severity == 'critical')
            lines.append(_('<b>%(n)s cảnh báo mới</b> (%(c)s nghiêm trọng):',
                           n=len(created), c=len(crit)))
            lines.append('<ul>')
            for a in (crit or created)[:8]:
                lines.append('<li>%s — %s</li>' % (a.name, a.description))
            if len(created) > 8:
                lines.append(_('<li>… và %s cảnh báo khác</li>',
                               len(created) - 8))
            lines.append('</ul>')
        if resolved:
            lines.append(_('<b>%s cảnh báo đã hết</b>.', len(resolved)))
        project.message_post(body=''.join(lines),
                             subject=_('Quét cảnh báo tiến độ'))

    @api.model
    def _cron_scan(self):
        """Quét hằng ngày mọi dự án có lịch thi công."""
        projects = self.env['re.project'].search(
            [('schedule_task_count', '>', 0)])
        total = 0
        for project in projects:
            created, _upd, _res = self._scan_project(project)
            total += len(created)
        return total

    # ------------------------------------------------------------------
    def action_acknowledge(self):
        self.write({'state': 'acknowledged',
                    'user_id': self.env.user.id})

    def action_resolve(self):
        self.write({'state': 'resolved',
                    'date_resolved': fields.Datetime.now()})

    def action_ignore(self):
        self.write({'state': 'ignored',
                    'date_resolved': fields.Datetime.now()})

    def action_reopen(self):
        self.write({'state': 'open', 'date_resolved': False})

    def action_open_subject(self):
        """Mở thẳng thứ đang có vấn đề: công việc, điểm giao, hay dự án."""
        self.ensure_one()
        if self.task_id:
            return {'type': 'ir.actions.act_window',
                    'res_model': 'project.task',
                    'res_id': self.task_id.id,
                    'views': [[False, 'form']]}
        if self.interface_id:
            return {'type': 'ir.actions.act_window',
                    'res_model': 'rp.interface',
                    'res_id': self.interface_id.id,
                    'views': [[False, 'form']]}
        return {'type': 'ir.actions.act_window',
                'res_model': 're.project',
                'res_id': self.project_id.id,
                'views': [[False, 'form']]}
