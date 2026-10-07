# -*- coding: utf-8 -*-
"""Tiến độ ở cấp DỰ ÁN, gom mọi hợp đồng.

Một dự án thường có nhiều gói thầu, mỗi gói lại nhiều hợp đồng với nhà
thầu khác nhau: gói cung cấp thiết bị của hãng, gói vận chuyển của đơn
vị logistics, gói lắp dựng của nhà thầu cơ giới. Lịch của từng hợp đồng
trả lời được "nhà thầu này có đúng hẹn không", nhưng KHÔNG trả lời được
"bao giờ xong dự án" — vì công việc quyết định ngày về đích nằm rải ở
nhiều hợp đồng, nối nhau qua các điểm bàn giao.

Ở đây gom hết lại: một ngày hoàn thành dự báo, một đường găng xuyên hợp
đồng, một con số trượt so với kế hoạch gốc.
"""
from odoo import _, api, fields, models


class ReProject(models.Model):
    _inherit = 're.project'

    schedule_task_ids = fields.One2many(
        'project.task', 'rp_project_id', string='Công việc (mọi hợp đồng)')
    schedule_task_count = fields.Integer(
        string='Số công việc', compute='_compute_schedule_rollup', store=True)
    schedule_contract_count = fields.Integer(
        string='Số hợp đồng có lịch',
        compute='_compute_schedule_rollup', store=True)
    schedule_forecast_end = fields.Date(
        string='Hoàn thành dự báo', compute='_compute_schedule_rollup',
        store=True,
        help='Ngày kết thúc muộn nhất trong kế hoạch hiện hành của MỌI '
             'hợp đồng thuộc dự án.')
    schedule_baseline_end = fields.Date(
        string='Hoàn thành theo baseline', compute='_compute_schedule_rollup',
        store=True)
    schedule_slip_days = fields.Integer(
        string='Trượt so baseline (ngày)', compute='_compute_schedule_rollup',
        store=True,
        help='Hoàn thành dự báo trừ hoàn thành theo kế hoạch gốc. Dương '
             'là trễ.')
    schedule_link_count = fields.Integer(
        string='Số quan hệ trước–sau', compute='_compute_link_rollup')
    schedule_link_violated_count = fields.Integer(
        string='Quan hệ lịch đang bị vi phạm', compute='_compute_link_rollup',
        help='Việc sau bắt đầu (hoặc kết thúc) sớm hơn mức quan hệ đã khai '
             'cho phép. Đường găng tính trên một mạng đang tự mâu thuẫn '
             'thì không đáng tin — sửa chỗ này trước.')
    schedule_link_ss_count = fields.Integer(
        string='Quan hệ chồng lấn (SS/FF)', compute='_compute_link_rollup')
    # KHÔNG lưu: giá trị đến từ hàm _rp_schedule_deadline() mà module
    # ngành ghi đè (nhà máy điện lấy ngày COD). Lưu lại thì lúc nâng cấp
    # rp_schedule nó được tính TRƯỚC khi module ngành vào registry, ra
    # rỗng, và không gì buộc nó tính lại.
    schedule_deadline = fields.Date(
        string='Mốc phải xong', compute='_compute_schedule_deadline',
        help='Ngày dự án buộc phải về đích theo cam kết. Đường găng toàn '
             'dự án lấy mốc này làm đích, nên chuỗi việc không kịp sẽ ra '
             'dư địa âm.')
    schedule_deadline_slip = fields.Integer(
        string='Trễ so mốc phải xong (ngày)',
        compute='_compute_schedule_rollup', store=True)

    schedule_deadline_task_id = fields.Many2one(
        'project.task', string='Mốc chịu lực',
        domain="[('rp_project_id', '=', id), ('is_milestone', '=', True)]",
        help='Công việc mang mốc cam kết (ví dụ COD). Trễ của dự án đo ở '
             'ĐÚNG mốc này, không đo ở ngày kết thúc muộn nhất — vì sau '
             'COD vẫn còn việc hợp lệ như bàn giao, hoàn công, TOC.')

    def _rp_schedule_deadline(self):
        """Ngày dự án buộc phải xong — đích của đường găng toàn dự án.

        Mặc định là ngày bàn giao dự kiến. Dự án có cam kết khác thì
        module ngành ghi đè hàm này (nhà máy điện: ngày COD).
        """
        self.ensure_one()
        return self.expected_handover_date

    @api.depends('expected_handover_date')
    def _compute_schedule_deadline(self):
        for rec in self:
            rec.schedule_deadline = rec._rp_schedule_deadline()

    @api.depends('schedule_task_ids.planned_end',
                 'schedule_task_ids.baseline_end',
                 'schedule_task_ids.rp_contract_id',
                 'schedule_deadline', 'schedule_deadline_task_id.planned_end')
    def _compute_schedule_rollup(self):
        for rec in self:
            tasks = rec.schedule_task_ids
            ends = [t.planned_end for t in tasks if t.planned_end]
            bases = [t.baseline_end for t in tasks if t.baseline_end]
            rec.schedule_task_count = len(tasks)
            rec.schedule_contract_count = len(tasks.mapped('rp_contract_id'))
            rec.schedule_forecast_end = max(ends) if ends else False
            rec.schedule_baseline_end = max(bases) if bases else False
            rec.schedule_slip_days = (
                (rec.schedule_forecast_end - rec.schedule_baseline_end).days
                if ends and bases else 0)
            # Đo trễ tại MỐC CHỊU LỰC nếu đã chỉ định; nếu chưa thì
            # tạm lấy ngày về đích muộn nhất.
            marker = (rec.schedule_deadline_task_id.planned_end
                      or rec.schedule_forecast_end)
            rec.schedule_deadline_slip = (
                (marker - rec.schedule_deadline).days
                if marker and rec.schedule_deadline else 0)

    def _compute_link_rollup(self):
        Link = self.env['rp.task.link']
        for rec in self:
            base = [('project_id', '=', rec.id)] if rec.id else [('id', '=', 0)]
            rec.schedule_link_count = Link.search_count(base)
            rec.schedule_link_violated_count = Link.search_count(
                base + [('is_violated', '=', True)])
            rec.schedule_link_ss_count = Link.search_count(
                base + [('link_type', 'in', ('SS', 'FF', 'SF'))])

    def _rp_schedule_markers(self):
        """Mốc vạch dọc trên Gantt: ngày phải xong + hôm nay.

        Module ngành bổ sung mốc riêng bằng cách ghi đè hàm này (nhà máy
        điện: ngày đóng điện, ngày COD).
        """
        self.ensure_one()
        marks = []
        deadline = self.schedule_deadline
        if deadline:
            marks.append({
                'date': fields.Date.to_string(deadline),
                'label': _('Phải xong: %s',
                           deadline.strftime('%d/%m/%Y')),
                'kind': 'deadline',
            })
        marks.append({
            'date': fields.Date.to_string(fields.Date.context_today(self)),
            'label': _('Hôm nay'),
            'kind': 'today',
        })
        # Vạch do người dùng tự khai trên công việc (cờ "Vạch trên trục
        # thời gian"). Nhờ vậy mỗi dự án tự chọn lấy vài ngày đáng để cả
        # phòng cùng nhìn, không phải chờ lập trình thêm loại mốc mới.
        for t in self.env['project.task'].search([
            ('rp_project_id', '=', self.id),
            ('rp_event_marker', '=', True),
            ('planned_end', '!=', False),
        ], order='planned_end'):
            marks.append({
                'date': fields.Date.to_string(t.planned_end),
                # Nhãn CHỈ tên việc, không kèm ngày: nhãn nằm ngang trên
                # trục nên hai vạch cách nhau vài tuần là chữ đè lên nhau,
                # mà ngày thì đọc ngay dưới trục rồi.
                'label': t.name,
                'kind': 'event',
            })
        return marks

    @api.model
    def rp_schedule_markers(self, project_id):
        """Cho Gantt gọi: trả mốc vạch dọc của dự án."""
        return self.browse(int(project_id))._rp_schedule_markers()

    @api.model
    def rp_milestone_brief(self, project_id):
        """Tóm tắt tiến độ theo MỐC, cho dải số liệu cố định trên Gantt.

        Đây là bộ câu hỏi một giám đốc dự án bị hỏi khi đứng trước ban
        lãnh đạo, xếp đúng thứ tự người ta hỏi:

          1. Bao giờ về đích, còn bao lâu, có trượt so kế hoạch gốc không?
          2. Đã đạt bao nhiêu mốc trên tổng số?
          3. Đang trễ mốc nào?
          4. Nút thắt nằm ở đâu — chậm chỗ nào thì chậm cả dự án?
          5. Sắp tới phải quyết cái gì?

        Trả về nguyên liệu thô (tên, ngày, số ngày), phần chữ nghĩa để
        giao diện lo, vì cùng bộ số này còn dùng cho bản in họp giao ban.
        """
        P = self.browse(int(project_id))
        today = fields.Date.context_today(self)
        Task = self.env['project.task']
        moc = Task.search([('rp_project_id', '=', P.id),
                           ('is_milestone', '=', True)])

        def _g(t):
            return t.rp_contract_id.tender_package_id.code or ''

        def _m(t, **kw):
            d = {
                'id': t.id,
                'name': t.name or '',
                # Định dạng sẵn kiểu Việt Nam: dải này để ĐỌC TRƯỚC
                # ĐÁM ĐÔNG, không phải để máy xử tiếp.
                'date': (t.planned_end.strftime('%d/%m/%Y')
                         if t.planned_end else ''),
                'package': _g(t),
            }
            d.update(kw)
            return d

        # 1. Về đích — mượn nhãn của _rp_schedule_markers để module ngành
        #    đặt tên gì (COD, phát điện thương mại…) thì hiện đúng tên đó.
        dl = next((m for m in P._rp_schedule_markers()
                   if m.get('kind') == 'deadline'), None)
        ve_dich = None
        if dl:
            ngay = fields.Date.to_date(dl['date'])
            ve_dich = {
                'label': dl['label'],
                'date': dl['date'],
                'days_left': (ngay - today).days,
            }

        # Trượt so kế hoạch gốc: lấy mốc TRƯỢT NHIỀU NHẤT, không lấy
        # trung bình — trung bình làm loãng đúng cái mốc đang gây hại.
        # Phân biệt "không trượt" với "CHƯA CHỐT baseline" — hai chuyện
        # khác hẳn nhau. Báo nhầm thành "bám đúng kế hoạch gốc" khi thật
        # ra chưa có gốc nào là nói sai với ban lãnh đạo.
        co_goc = bool(moc.filtered(lambda t: t.baseline_end))
        truot = moc.filtered(lambda t: (t.baseline_slip_days or 0) > 0)
        truot_max = max(truot.mapped('baseline_slip_days')) if truot else 0

        xong = moc.filtered(lambda t: t.exec_status == 'done')
        tre = moc.filtered(lambda t: t.exec_status == 'late')

        # 4. Nút thắt: trong các MỐC, cái có tổng dự trữ thấp nhất. Dự trữ
        #    âm nghĩa là không còn kịp mốc phải xong — số càng âm càng gấp.
        cpm = {}
        try:
            cpm = Task.rp_compute_project_critical_path(P.id) or {}
        except Exception:                      # noqa: BLE001
            cpm = {}
        co_tf = [(cpm[t.id]['tf'], t) for t in moc
                 if cpm.get(t.id) and cpm[t.id].get('tf') is not None]
        nut_that = None
        if co_tf:
            tf, t = min(co_tf, key=lambda x: x[0])
            nut_that = _m(t, float=tf)
        tf_all = [v['tf'] for v in cpm.values() if v.get('tf') is not None]

        return {
            'project': P.display_name,
            'today': fields.Date.to_string(today),
            've_dich': ve_dich,
            'tong': len(moc),
            'xong': len(xong),
            'tre': len(tre),
            'phan_tram': round(len(xong) * 100.0 / len(moc)) if moc else 0,
            'co_goc': co_goc,
            'truot_max': truot_max,
            'truot_count': len(truot),
            'tre_ds': [
                _m(t, days=(today - t.planned_end).days)
                for t in tre.sorted('planned_end')[:3] if t.planned_end
            ],
            'ke_tiep': [
                _m(t, days=(t.planned_end - today).days)
                for t in moc.filtered(
                    lambda x: x.exec_status != 'done' and x.planned_end
                    and x.planned_end >= today).sorted('planned_end')[:2]
            ],
            'nut_that': nut_that,
            'gang': sum(1 for v in cpm.values() if v.get('critical')),
            'du_dia': min(tf_all) if tf_all else 0,
            'theo_goi': sorted([
                {
                    'code': g,
                    'tong': len(ds),
                    'xong': len(ds.filtered(lambda t: t.exec_status == 'done')),
                    'tre': len(ds.filtered(lambda t: t.exec_status == 'late')),
                }
                for g, ds in [
                    (g, moc.filtered(lambda t, g=g: _g(t) == g))
                    for g in {_g(t) for t in moc}
                ]
            ], key=lambda x: -x['tong']),
        }

    def action_compute_project_cpm(self):
        """Tính đường găng xuyên hợp đồng cho dự án."""
        self.ensure_one()
        res = self.env['project.task'].rp_compute_project_critical_path(self.id)
        n_crit = sum(1 for v in res.values() if v['critical'])
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': _(
                    'Đã tính đường găng toàn dự án: %(n)s công việc, '
                    '%(c)s việc găng.', n=len(res), c=n_crit),
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }

    def action_fill_task_seq(self):
        """Cấp STT cho công việc chưa có số — KHÔNG đụng việc đã có.

        Việc mới tự nhận số kế tiếp ngay khi tạo, nên nút này chỉ cần
        dùng cho lịch nhập từ trước khi có trường STT.
        """
        self.ensure_one()
        n = self.env['project.task'].rp_fill_missing_seq(project_id=self.id)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success' if n else 'info',
                'message': (_('Đã cấp STT cho %(n)s công việc chưa có số.',
                              n=n) if n
                            else _('Mọi công việc đều đã có STT.')),
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }

    def action_open_schedule_links(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Quan hệ trước–sau — %s', self.name),
            'res_model': 'rp.task.link',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }

    def action_open_violated_links(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Quan hệ lịch đang bị vi phạm — %s', self.name),
            'res_model': 'rp.task.link',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id),
                       ('is_violated', '=', True)],
        }

    def action_links_to_ss(self):
        """Chuyển các quan hệ FS đang bị chồng lấn sang SS với lệch thật.

        Lịch fast-track thường ĐÚNG, chỉ là quan hệ khai sai loại: hai
        việc chồng lấn nhau mà vẫn ghi finish-to-start. Cách xử lý sai là
        xoá quan hệ cho hết báo lỗi — mạng phụ thuộc rỗng dần và đường
        găng thành vô nghĩa. Cách đúng là giữ quan hệ, đổi sang SS và lấy
        độ lệch đúng bằng khoảng cách hai ngày bắt đầu.
        """
        self.ensure_one()
        links = self.env['rp.task.link'].search([
            ('project_id', '=', self.id), ('is_violated', '=', True),
            ('link_type', '=', 'FS')])
        added = links.action_set_ss_from_dates()
        self.env['project.task'].rp_compute_project_critical_path(self.id)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': _(
                    'Đã chuyển %(n)s quan hệ FS bị chồng lấn sang SS kèm '
                    'độ lệch thật, thêm %(f)s nhánh FF để vỡ thời lượng '
                    'cũng truyền được, và tính lại đường găng.',
                    n=len(links), f=len(added)),
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }

    def action_open_project_gantt(self):
        """Mở Gantt gom lịch mọi hợp đồng của dự án."""
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'rp_schedule.gantt',
            'name': _('Tiến độ dự án — %s', self.name),
            'params': {'project_id': self.id},
            'context': {'rp_project_id': self.id},
        }

    def action_open_project_tasks(self):
        self.ensure_one()
        panel = self.env.ref('rp_schedule.view_task_search_rp_panel',
                             raise_if_not_found=False)
        return {
            'type': 'ir.actions.act_window',
            'name': _('Công việc — %s', self.name),
            'res_model': 'project.task',
            'view_mode': 'list,form',
            'domain': [('rp_project_id', '=', self.id)],
            # Pane lọc bên trái: gói thầu / hợp đồng của chính dự án này.
            'search_view_id': [panel.id, 'search'] if panel else False,
            'context': {'search_default_rp_group_contract': 1},
        }
