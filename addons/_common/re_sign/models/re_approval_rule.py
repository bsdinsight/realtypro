# -*- coding: utf-8 -*-
"""Ma trận phê duyệt: chứng từ nào, giá trị bao nhiêu, thì ai phải ký.

Không phải một bảng cấu hình cho có. Thứ nó trả lời là câu người ta hỏi
nhau suốt ở công trường: *"biên bản này đủ chữ ký chưa?"* — và trước
đây câu đó chỉ trả lời được bằng cách nhớ.

Luật khớp theo NGƯỠNG GIÁ TRỊ vì đó là cách các ban quản lý phân quyền
thật: biên bản vài trăm triệu thì chỉ huy trưởng ký là xong, vài chục tỷ
thì phải lên tới giám đốc. Để một luật duy nhất cho mọi giá trị thì
hoặc là chặn những thứ lẽ ra trôi được, hoặc là thả những thứ lẽ ra
phải chặn.
"""
from odoo import _, api, fields, models

from odoo.addons.re_sign.models.re_signature import VAI

# Ô chọn chứng từ để MỞ, không bó vào vài model định sẵn: một màn cấu
# hình chỉ cho chọn hai thứ thì nhìn như đồ gắn cứng chứ không phải cấu
# hình, và mỗi lần khách muốn thêm chứng từ lại phải sửa mã.
#
# Đổi lại phải nói thật: luật chỉ CÓ HIỆU LỰC trên model đã bật ký (kế
# thừa ``re.signable``). Khai cho model chưa bật thì luật vẫn lưu nhưng
# không ràng buộc gì — nên có cờ ``is_signable`` và dải cảnh báo, chứ
# không để người dùng khai xong tưởng đã xong.
DOMAIN_MODEL = [
    ('transient', '=', False),
    ('abstract', '=', False),
    '|', '|',
    ('model', '=like', 'rp.%'),
    ('model', '=like', 're.%'),
    ('model', '=like', 'eam.%'),
]


class ReApprovalRule(models.Model):
    _name = 're.approval.rule'
    _description = 'Luật phê duyệt chứng từ'
    _order = 'res_model, sequence, id'

    name = fields.Char(
        string='Tên bước duyệt', required=True,
        help='Viết cho người đọc hiểu ngay, ví dụ "Trên 10 tỷ: Giám đốc '
             'dự án phải ký".')
    res_model_id = fields.Many2one(
        'ir.model', string='Áp cho chứng từ', required=True,
        ondelete='cascade', domain=DOMAIN_MODEL,
        help='Chọn loại chứng từ muốn đặt luật phê duyệt.')
    res_model = fields.Char(
        string='Mã model', related='res_model_id.model',
        store=True, index=True, readonly=True)
    is_signable = fields.Boolean(
        string='Đã bật ký', compute='_compute_is_signable', store=True,
        help='Chứng từ đã gắn chức năng ký hay chưa. Chưa gắn thì luật '
             'vẫn lưu được nhưng chưa ràng buộc gì.')
    sequence = fields.Integer(
        string='Thứ tự', default=10,
        help='Thứ tự trình bày và thứ tự ký mong muốn. KHÔNG ép ký theo '
             'đúng thứ tự — thực tế chữ ký hay về lệch thứ tự, ép thì '
             'người dùng quay ra ký khống cho đủ.')
    role = fields.Selection(
        VAI, string='Vai phải ký', required=True, default='owner')
    required = fields.Boolean(
        string='Bắt buộc', default=True,
        help='Bỏ tích thì bước này chỉ để nhắc, thiếu cũng không bị kêu.')

    amount_min = fields.Float(
        string='Giá trị từ', digits=(16, 2),
        help='Luật chỉ áp khi giá trị chứng từ ĐẠT mức này. Để 0 là '
             'không có cận dưới.')
    amount_max = fields.Float(
        string='Đến dưới', digits=(16, 2),
        help='Luật thôi áp khi giá trị bằng hoặc vượt mức này. Để 0 là '
             'không có cận trên.')
    currency_id = fields.Many2one(
        'res.currency', string='Tiền tệ',
        default=lambda self: self.env.company.currency_id)

    project_id = fields.Many2one(
        're.project', string='Chỉ áp cho dự án',
        help='Để trống là áp cho mọi dự án.')
    group_id = fields.Many2one(
        'res.groups', string='Nhóm được ký bước này',
        help='Để trống là ai cũng ký được bước này. Đây là thông tin '
             'hướng dẫn, KHÔNG phải hàng rào kỹ thuật — hàng rào thật '
             'nằm ở quyền trên chính chứng từ.')
    note = fields.Char(string='Ghi chú')
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', string='Công ty',
        default=lambda self: self.env.company)

    # ------------------------------------------------------------------
    @api.model
    def _luat_cho(self, doc):
        """Các luật áp cho một chứng từ cụ thể."""
        if 'signature_ids' not in doc._fields:
            return self.browse()
        tien = doc._approval_amount()
        du_an = doc._approval_project()
        luat = self.search([('res_model', '=', doc._name)])
        return luat.filtered(lambda r: (
            (not r.amount_min or tien >= r.amount_min)
            and (not r.amount_max or tien < r.amount_max)
            and (not r.project_id or r.project_id == du_an)
        ))

    @api.depends('res_model')
    def _compute_is_signable(self):
        for r in self:
            m = r.res_model
            r.is_signable = bool(
                m and m in self.env
                and 'signature_ids' in self.env[m]._fields)

    @api.constrains('amount_min', 'amount_max')
    def _check_nguong(self):
        for r in self:
            if r.amount_max and r.amount_min and r.amount_max <= r.amount_min:
                raise models.ValidationError(_(
                    'Bước "%s": "Đến dưới" phải lớn hơn "Giá trị từ", nếu '
                    'không thì luật không bao giờ khớp chứng từ nào.'
                ) % r.name)

    def name_get(self):
        res = []
        vai = dict(VAI)
        for r in self:
            ten = '%s — %s' % (r.name, vai.get(r.role, r.role))
            res.append((r.id, ten))
        return res
