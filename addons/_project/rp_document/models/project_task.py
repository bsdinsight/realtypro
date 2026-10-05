# -*- coding: utf-8 -*-
"""Cổng hồ sơ nhìn từ lịch thi công.

Đây là chỗ sổ hồ sơ trả tiền cho công sức ghi chép: một công việc có thể
đúng ngày trên Gantt mà vẫn KHÔNG ĐƯỢC PHÉP khởi công, vì hồ sơ của nó
chưa qua điều 5.2. Chừng nào chưa nối hai thứ lại thì ban điều hành vẫn
hỏi "sao chưa làm" và nhà thầu vẫn trả lời "đang chờ duyệt", mỗi bên một
sổ riêng.

Quy ước ba con số:

* **Được thi công từ** — ngày muộn nhất trong các cổng của việc. Chỉ có
  giá trị khi MỌI hồ sơ của việc đều đã biết ngày; thiếu một cái là để
  trống, vì cái chưa biết mới là cái quyết định.
* **Chưa đủ hồ sơ** — còn ít nhất một hồ sơ mà ngày mở cổng phụ thuộc vào
  hành động của người khác (chưa trình, bị trả lại, hoặc đang chờ phê
  duyệt). Hồ sơ chỉ trình để xem xét thì không tính, vì chỉ cần hết hạn.
* **Chờ hồ sơ (ngày)** — cố ý KHÔNG lưu: nó đo theo ngày hôm nay, mà số
  đã lưu thì không tự già đi. Muốn lọc danh sách thì lọc trên ngày khởi
  công kế hoạch, đó là mốc cố định.
"""
from odoo import _, api, fields, models


class ProjectTask(models.Model):
    _inherit = 'project.task'

    doc_gate_ids = fields.Many2many(
        'rp.document', 'rp_document_task_rel', 'task_id', 'document_id',
        string='Hồ sơ phải có trước khi khởi công')
    doc_gate_count = fields.Integer(
        string='Số hồ sơ chặn', compute='_compute_doc_gate', store=True)
    doc_gate_ready_date = fields.Date(
        string='Được thi công từ', compute='_compute_doc_gate', store=True,
        help='Ngày muộn nhất trong các cổng hồ sơ của công việc này.')
    doc_gate_blocked = fields.Boolean(
        string='Chưa đủ hồ sơ để khởi công', compute='_compute_doc_gate',
        store=True, index=True)
    doc_gate_slip_days = fields.Integer(
        string='Chờ hồ sơ (ngày)', compute='_compute_doc_gate_slip',
        help='Số ngày mà hồ sơ về sau ngày khởi công kế hoạch. Việc đã đến '
             'ngày khởi công mà hồ sơ chưa xong thì đếm từ hôm nay.')

    @api.depends('doc_gate_ids.gate_date', 'doc_gate_ids.gate_certain',
                 'doc_gate_ids.review_track', 'doc_gate_ids.state')
    def _compute_doc_gate(self):
        for rec in self:
            gates = rec.doc_gate_ids.filtered(
                lambda d: d.review_track != 'info' and d.state != 'cancelled')
            rec.doc_gate_count = len(gates)
            if not gates:
                rec.doc_gate_blocked = False
                rec.doc_gate_ready_date = False
                continue
            rec.doc_gate_blocked = any(not g.gate_certain for g in gates)
            dates = [g.gate_date for g in gates if g.gate_date]
            # Thiếu một ngày là chưa biết được ngày khởi công — để trống,
            # chứ lấy ngày muộn nhất của phần đã biết thì ra số lạc quan sai.
            rec.doc_gate_ready_date = (max(dates) if len(dates) == len(gates)
                                       else False)

    def _compute_doc_gate_slip(self):
        today = fields.Date.context_today(self)
        for rec in self:
            ref = rec.doc_gate_ready_date or (
                today if rec.doc_gate_blocked else False)
            rec.doc_gate_slip_days = (
                (ref - rec.planned_start).days
                if ref and rec.planned_start and ref > rec.planned_start
                else 0)

    def action_open_doc_gates(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Hồ sơ của công việc'),
            'res_model': 'rp.document',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.doc_gate_ids.ids)],
        }
