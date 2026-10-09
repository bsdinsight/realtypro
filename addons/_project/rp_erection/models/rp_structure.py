# -*- coding: utf-8 -*-
from odoo import api, fields, models


class RpStructure(models.Model):
    """Phần trăm VẬT LÝ của hạng mục, suy từ số vị trí đã qua cổng.

    KHÔNG đè lên ``progress_percent``
    ---------------------------------
    Trường cũ tính theo *giá trị nghiệm thu đã duyệt / dự toán* — đó là
    tiến độ **thanh toán**. Trường ở đây đếm *bao nhiêu vị trí đã qua
    cổng* — tiến độ **vật lý**. Hai con số khác nhau là bình thường, và
    **khoảng cách giữa chúng chính là thông tin**: việc đã làm xong
    ngoài hiện trường mà chưa nghiệm thu được, tức chưa ra tiền.

    Trộn hai cái làm một sẽ mất đúng khoảng cách đó — thứ duy nhất chỉ ra
    hồ sơ đang tắc ở đâu.
    """
    _inherit = 'rp.structure'

    erection_gate_ids = fields.One2many(
        'rp.erection.gate', 'structure_id', string='Cổng dựng máy')
    erection_total = fields.Integer(
        string='Tổng ô cần qua', compute='_compute_erection')
    erection_done = fields.Integer(
        string='Ô đã qua', compute='_compute_erection')
    erection_percent = fields.Float(
        string='% vật lý (dựng máy)', compute='_compute_erection',
        digits=(16, 1), aggregator=False,
        help='Đếm từ sổ dựng máy: bao nhiêu vị trí đã qua cổng. KHÁC '
             '"% hoàn thành" vốn tính theo giá trị nghiệm thu đã duyệt. '
             'Chênh lệch giữa hai số là phần đã làm mà chưa ra tiền.')
    erection_gap = fields.Float(
        string='Chênh vật lý − thanh toán', compute='_compute_erection',
        digits=(16, 1), aggregator=False,
        help='Dương nghĩa là hiện trường đi trước hồ sơ: việc đã xong mà '
             'chưa nghiệm thu được. Âm nghĩa là đã nghiệm thu nhiều hơn '
             'phần dựng xong — đáng soi lại.')

    @api.depends('erection_gate_ids.step_ids.state', 'progress_percent')
    def _compute_erection(self):
        for s in self:
            ds = s.erection_gate_ids.mapped('step_ids')
            s.erection_total = len(ds)
            s.erection_done = len(ds.filtered(lambda x: x.state == 'done'))
            s.erection_percent = (s.erection_done / s.erection_total * 100.0
                                  if s.erection_total else 0.0)
            s.erection_gap = (s.erection_percent - (s.progress_percent or 0.0)
                              if s.erection_total else 0.0)
