# -*- coding: utf-8 -*-
"""rp.tender.eval.criterion — Tiêu chuẩn đánh giá HSDT (Phase 5.3).

3 nhóm tiêu chuẩn theo Luật Đấu thầu VN:
- capacity: Năng lực & kinh nghiệm (số năm, HĐ tương tự, tài chính,
  nhân sự, thiết bị)
- technical: Kỹ thuật (biện pháp thi công, tiến độ, chất lượng)
- price: Giá (phương pháp đánh giá giá thấp nhất / giá đánh giá)

Mỗi criterion có:
- weight: trọng số (Float — user tự định nghĩa scale, vd 0-100 hay
  0-10). Không enforce sum vì có thể là điểm thô hoặc %.
- is_mandatory: bắt buộc đạt — nếu không, NT bị loại ngay
- description: chi tiết tiêu chí + cách chấm

Phase 5.3 ship: chỉ define criteria. P5.4+ sẽ thêm scoring per bidder
(bidder × criterion = score line) nếu cần chấm chi tiết.
"""

from odoo import api, fields, models
from odoo.exceptions import ValidationError


CRITERION_KINDS = [
    ('capacity', 'Năng lực & kinh nghiệm'),
    ('technical', 'Kỹ thuật'),
    ('price', 'Giá'),
]


class RpTenderEvalCriterion(models.Model):
    _name = 'rp.tender.eval.criterion'
    _description = 'Tender Evaluation Criterion / Tiêu chuẩn đánh giá HSDT'
    _order = 'package_id, kind, sequence, id'

    package_id = fields.Many2one(
        'rp.tender.package', string='Gói thầu',
        required=True, ondelete='cascade', index=True,
    )
    sequence = fields.Integer(default=10)

    kind = fields.Selection(
        CRITERION_KINDS,
        string='Nhóm tiêu chuẩn',
        required=True, default='capacity',
    )
    name = fields.Char(
        string='Tên tiêu chí', required=True, translate=True,
        help='Vd: "Số năm hoạt động", "Biện pháp thi công", '
             '"Phương pháp đánh giá giá thấp nhất".',
    )
    weight = fields.Float(
        string='Trọng số', digits=(5, 2), default=10.0,
        help='Trọng số tiêu chí. User tự định nghĩa scale (vd 0-100 '
             'hay 0-10). Không enforce sum vì có thể là điểm thô.',
    )
    is_mandatory = fields.Boolean(
        string='Bắt buộc đạt',
        help='Nếu True, NT không đạt tiêu chí này → bị loại ngay '
             'không cần chấm tiếp các tiêu chí khác.',
    )
    description = fields.Text(
        string='Chi tiết tiêu chí',
        translate=True,
        help='Mô tả chi tiết tiêu chí + cách chấm. Vd: "Tối thiểu '
             '10 năm; 5-10 năm: 50%, >10 năm: 100% điểm".',
    )

    @api.constrains('weight')
    def _check_weight_non_negative(self):
        for c in self:
            if c.weight < 0:
                raise ValidationError(
                    f'Trọng số "{c.name}" phải >= 0.')
