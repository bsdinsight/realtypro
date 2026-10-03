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
        return marks

    @api.model
    def rp_schedule_markers(self, project_id):
        """Cho Gantt gọi: trả mốc vạch dọc của dự án."""
        return self.browse(int(project_id))._rp_schedule_markers()

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
