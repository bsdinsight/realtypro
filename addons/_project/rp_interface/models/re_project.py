# -*- coding: utf-8 -*-
"""Sổ ranh giới gói thầu nhìn từ cấp dự án, và cách dựng sổ từ lịch có sẵn."""
from odoo import _, api, fields, models

# Đoán loại ranh giới từ tên công việc bên giao. Chỉ là điểm xuất phát
# để người quản lý dự án sửa lại, không phải phán quyết.
TYPE_HINTS = [
    ('document', ('hồ sơ', 'bản vẽ', 'thiết kế', 'duyệt', 'phê duyệt',
                  'tài liệu', 'hoàn công', 'quyết toán')),
    ('approval', ('nghiệm thu', 'kiểm định', 'thí nghiệm', 'chứng chỉ',
                  'fat', 'chấp thuận')),
    ('access', ('mặt bằng', 'đường', 'bãi', 'giải phóng', 'gpmb',
                'lối vào')),
    ('system', ('đấu nối', 'đóng điện', 'cáp', 'scada', 'hoà lưới')),
    ('utility', ('điện thi công', 'nước thi công', 'cấp điện',
                 'cấp nước')),
]


class ReProject(models.Model):
    _inherit = 're.project'

    interface_ids = fields.One2many(
        'rp.interface', 'project_id', string='Điểm bàn giao giữa các gói thầu')
    interface_count = fields.Integer(
        string='Số điểm bàn giao', compute='_compute_interface_stats')
    interface_open_count = fields.Integer(
        string='Điểm bàn giao chưa đóng', compute='_compute_interface_stats')
    interface_conflict_count = fields.Integer(
        string='Điểm bàn giao lịch mâu thuẫn',
        compute='_compute_interface_stats')

    @api.depends('interface_ids.state', 'interface_ids.is_conflict')
    def _compute_interface_stats(self):
        for rec in self:
            ifs = rec.interface_ids
            rec.interface_count = len(ifs)
            open_ifs = ifs.filtered(
                lambda i: i.state not in ('delivered', 'closed', 'cancelled'))
            rec.interface_open_count = len(open_ifs)
            rec.interface_conflict_count = len(
                open_ifs.filtered('is_conflict'))

    # ------------------------------------------------------------------
    def _guess_interface_type(self, task):
        low = (task.name or '').lower()
        for itype, words in TYPE_HINTS:
            if any(w in low for w in words):
                return itype
        return 'physical'

    def action_scan_interfaces(self):
        """Dựng sổ ranh giới gói thầu từ chính lịch thi công đang có.

        Mọi quan hệ trước-sau NỐI HAI HỢP ĐỒNG KHÁC NHAU đều là một điểm
        giao đã tồn tại trên thực tế — chỉ là chưa ai ghi vào sổ. Quét
        một lượt để có sổ ngay, rồi người quản lý dự án bổ sung điều kiện
        nghiệm thu và người phụ trách hai bên.

        Chạy lại được: điểm bàn giao đã có (theo cặp việc) thì bỏ qua.
        """
        self.ensure_one()
        Task = self.env['project.task']
        tasks = Task.search([('rp_project_id', '=', self.id)])
        existing = {
            (i.from_task_id.id, i.to_task_id.id)
            for i in self.env['rp.interface'].search([
                ('project_id', '=', self.id),
                ('from_task_id', '!=', False),
                ('to_task_id', '!=', False)])
        }
        vals_list = []
        for succ in tasks:
            for pred in succ.predecessor_ids:
                if not (pred.rp_contract_id and succ.rp_contract_id):
                    continue
                if pred.rp_contract_id == succ.rp_contract_id:
                    continue
                if (pred.id, succ.id) in existing:
                    continue
                vals_list.append({
                    'name': _('%(a)s → %(b)s', a=pred.name, b=succ.name),
                    'project_id': self.id,
                    'from_contract_id': pred.rp_contract_id.id,
                    'to_contract_id': succ.rp_contract_id.id,
                    'from_task_id': pred.id,
                    'to_task_id': succ.id,
                    'interface_type': self._guess_interface_type(pred),
                    # Việc nằm trên đường găng toàn dự án thì điểm bàn giao
                    # của nó chính là chỗ chịu lực.
                    'criticality': ('critical'
                                    if succ.is_project_critical
                                    or pred.is_project_critical
                                    else 'medium'),
                    'state': 'identified',
                })
        before = self.interface_count
        created = self.env['rp.interface'].create(vals_list)
        self.invalidate_recordset(['interface_ids'])
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success' if created else 'warning',
                'message': (
                    _('Đã ghi thêm %(n)s điểm bàn giao từ lịch thi công. '
                      'Tổng cộng %(t)s.',
                      n=len(created), t=before + len(created))
                    if created else
                    _('Không có điểm bàn giao mới: mọi quan hệ nối hai hợp '
                      'đồng đã nằm trong sổ.')),
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }

    def action_open_interfaces(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Ranh giới gói thầu — %s', self.name),
            'res_model': 'rp.interface',
            'view_mode': 'list,kanban,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }
