# -*- coding: utf-8 -*-
"""Bản tổng hợp dự án — một kỳ, một bản ghi, số đã chốt.

Mỗi phòng ban đều hỏi cùng một dự án nhưng cần lát cắt khác nhau: Ban
QLDA hỏi tiến độ và vướng mắc, Tài chính hỏi cam kết và dự báo chi,
Mua sắm hỏi hàng dài hạn và bảo lãnh, Lãnh đạo hỏi "có về đích đúng hẹn
và trong ngân sách không". Nếu ai cũng tự đi lọc thì mỗi người ra một
con số, và cuộc họp biến thành tranh luận về số liệu.

Bản ghi này chốt toàn bộ chỉ số của một dự án tại MỘT thời điểm, để:

* mọi phòng đọc cùng một bộ số;
* so sánh được kỳ này với kỳ trước (chính là thứ báo cáo quản trị cần,
  chứ không phải ảnh chụp hiện tại);
* xuất Excel một phát, không phải ghép tay từ năm màn hình.

Số được chụp lại chứ không tính động: báo cáo tháng 10 phải giữ nguyên
con số của tháng 10 kể cả khi lịch đổi vào tháng 11.
"""
from odoo import _, api, fields, models


class RpProjectBrief(models.Model):
    _name = 'rp.project.brief'
    _description = 'Bản tổng hợp dự án theo kỳ'
    _order = 'date_snapshot desc, id desc'

    name = fields.Char(string='Kỳ báo cáo', required=True)
    project_id = fields.Many2one(
        're.project', string='Dự án', required=True, index=True,
        ondelete='cascade')
    date_snapshot = fields.Date(
        string='Ngày chốt số', required=True,
        default=fields.Date.context_today)
    currency_id = fields.Many2one(
        'res.currency', related='project_id.currency_id', store=True)
    note = fields.Text(string='Nhận định')

    # --- Tiến độ (Ban QLDA) -------------------------------------------
    task_count = fields.Integer(string='Số công việc')
    contract_count = fields.Integer(string='Số hợp đồng có lịch')
    forecast_end = fields.Date(string='Về đích dự báo')
    deadline = fields.Date(string='Mốc phải xong')
    deadline_slip = fields.Integer(string='Trễ so mốc (ngày)')
    baseline_slip = fields.Integer(string='Trượt so kế hoạch gốc (ngày)')
    critical_count = fields.Integer(string='Số việc trên đường găng')
    worst_float = fields.Integer(string='Dư địa xấu nhất (ngày)')
    task_late_count = fields.Integer(string='Số việc đang trượt')

    # --- Phối hợp (Ban QLDA) ------------------------------------------
    interface_count = fields.Integer(string='Số điểm giao')
    interface_conflict_count = fields.Integer(string='Điểm giao mâu thuẫn')
    alert_open_count = fields.Integer(string='Cảnh báo đang mở')
    alert_critical_count = fields.Integer(string='Cảnh báo nghiêm trọng')

    # --- Tiền (Tài chính) ---------------------------------------------
    budget_bac = fields.Monetary(string='Ngân sách duyệt (BAC)')
    committed = fields.Monetary(string='Đã cam kết theo hợp đồng')
    variation_approved = fields.Monetary(string='Phát sinh đã duyệt')
    variation_pending = fields.Monetary(string='Phát sinh đang chờ')
    cost_forecast = fields.Monetary(string='Dự báo chi phí cuối kỳ')
    budget_gap = fields.Monetary(string='Chênh so ngân sách')

    # --- Hợp đồng (Mua sắm & pháp chế) --------------------------------
    claim_count = fields.Integer(string='Số khiếu nại')
    claim_open_count = fields.Integer(string='Khiếu nại đang mở')
    eot_days_granted = fields.Integer(string='Tổng ngày đã gia hạn')
    ld_exposure = fields.Monetary(string='Phạt chậm dự kiến')
    variation_open_count = fields.Integer(string='Phát sinh đang xử lý')

    # ------------------------------------------------------------------
    @api.model
    def _capture(self, project, date=None, name=None):
        """Chụp toàn bộ chỉ số của dự án tại thời điểm hiện tại."""
        date = date or fields.Date.context_today(self)
        Task = self.env['project.task']
        cpm = Task.rp_compute_project_critical_path(project.id)
        tasks = Task.search([('rp_project_id', '=', project.id)])
        contracts = self.env['rp.contract'].search(
            [('project_id', '=', project.id)])
        claims = self.env['rp.claim'].search(
            [('project_id', '=', project.id)])
        project.invalidate_recordset()
        vals = {
            'name': name or _('Tổng hợp %s', date.strftime('%m/%Y')),
            'project_id': project.id,
            'date_snapshot': date,
            # tiến độ
            'task_count': project.schedule_task_count,
            'contract_count': project.schedule_contract_count,
            'forecast_end': project.schedule_forecast_end,
            'deadline': project.schedule_deadline,
            'deadline_slip': project.schedule_deadline_slip,
            'baseline_slip': project.schedule_slip_days,
            'critical_count': sum(1 for v in cpm.values() if v['critical']),
            'worst_float': (min(v['tf'] for v in cpm.values())
                            if cpm else 0),
            'task_late_count': len(tasks.filtered(
                lambda t: t.baseline_slip_days > 0)),
            # phối hợp
            'interface_count': project.interface_count,
            'interface_conflict_count': project.interface_conflict_count,
            'alert_open_count': project.alert_open_count,
            'alert_critical_count': project.alert_critical_count,
            # tiền
            'budget_bac': project.total_bac,
            'committed': project.contract_committed_total,
            'variation_approved': project.variation_approved_total,
            'variation_pending': project.variation_pending_total,
            'cost_forecast': project.cost_forecast_total,
            'budget_gap': project.budget_gap,
            # hợp đồng
            'claim_count': len(claims),
            'claim_open_count': len(claims.filtered(
                lambda c: c.state not in ('rejected', 'closed'))),
            'eot_days_granted': sum(contracts.mapped('eot_days_granted')),
            'ld_exposure': sum(contracts.mapped('ld_amount_exposure')),
            'variation_open_count': project.variation_open_count,
        }
        return self.create(vals)

    @api.model
    def _cron_monthly(self):
        """Chốt số đầu mỗi tháng cho mọi dự án có lịch thi công."""
        projects = self.env['re.project'].search(
            [('schedule_task_count', '>', 0)])
        for project in projects:
            self._capture(project)
        return len(projects)

    def action_open_project(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 're.project',
            'res_id': self.project_id.id,
            'views': [[False, 'form']],
        }
