# -*- coding: utf-8 -*-
"""Một lượt ký lên một chứng từ.

Điểm chịu lực không phải tấm ảnh chữ ký mà là ``doc_hash``: mã băm của
phần NỘI DUNG CHỊU TRÁCH NHIỆM tại đúng thời điểm ký. Không có nó thì
ký xong sửa số ở dưới, chữ ký vẫn nằm đó như chưa có gì xảy ra — tức là
một chữ ký không bảo chứng điều gì.
"""
import hashlib

from odoo import _, api, fields, models

VAI = [
    ('owner', 'Chủ đầu tư'),
    ('contractor', 'Nhà thầu'),
    ('supervisor', 'Tư vấn giám sát'),
    ('designer', 'Tư vấn thiết kế'),
    ('other', 'Khác'),
]


class ReSignature(models.Model):
    _name = 're.signature'
    _description = 'Chữ ký duyệt'
    _order = 'signed_on desc, id desc'
    _rec_name = 'signer_name'

    # Nối kiểu chung (res_model/res_id) thay vì m2o cho từng loại chứng
    # từ: thêm một chứng từ ký được về sau chỉ là kế thừa mixin, không
    # phải sửa bảng này.
    res_model = fields.Char(string='Model', required=True, index=True)
    res_id = fields.Integer(string='Bản ghi', required=True, index=True)
    res_name = fields.Char(string='Chứng từ', compute='_compute_res_name')

    role = fields.Selection(VAI, string='Vai', required=True, default='owner')
    signer_name = fields.Char(string='Người ký', required=True)
    signer_title = fields.Char(string='Chức danh')
    partner_id = fields.Many2one('res.partner', string='Thuộc đơn vị')

    signature = fields.Binary(string='Chữ ký', required=True, attachment=True)
    signed_on = fields.Datetime(
        string='Ký lúc', required=True, default=fields.Datetime.now,
        readonly=True)
    signed_uid = fields.Many2one(
        'res.users', string='Tài khoản ký', required=True, readonly=True,
        default=lambda self: self.env.user)
    signed_ip = fields.Char(string='Địa chỉ IP', readonly=True)

    doc_hash = fields.Char(
        string='Mã băm lúc ký', readonly=True, required=True,
        help='SHA-256 của phần nội dung chịu trách nhiệm tại thời điểm '
             'ký. Nội dung đổi thì băm lại ra khác, và chữ ký tự báo '
             'không còn hợp lệ.')
    is_valid = fields.Boolean(
        string='Còn hợp lệ', compute='_compute_valid')
    invalid_reason = fields.Char(
        string='Vì sao không còn hợp lệ', compute='_compute_valid')

    # ------------------------------------------------------------------
    @api.model
    def _bam(self, payload):
        return hashlib.sha256((payload or '').encode('utf-8')).hexdigest()

    def _doc(self):
        """Bản ghi chứng từ, hoặc recordset rỗng nếu đã bị xoá."""
        self.ensure_one()
        if self.res_model not in self.env:
            return None
        return self.env[self.res_model].browse(self.res_id).exists()

    @api.depends('res_model', 'res_id')
    def _compute_res_name(self):
        for rec in self:
            doc = rec._doc()
            rec.res_name = doc.display_name if doc else _('(đã xoá)')

    def _compute_valid(self):
        # KHÔNG khai depends: giá trị phụ thuộc nội dung của một model
        # BẤT KỲ, không liệt kê trước được. Trường không lưu nên mỗi lần
        # đọc là tính lại — đúng điều cần, vì câu hỏi "có còn hợp lệ
        # không" phải trả lời theo hiện tại chứ không theo lúc ghi.
        for rec in self:
            doc = rec._doc()
            if not doc:
                rec.is_valid = False
                rec.invalid_reason = _('Chứng từ đã bị xoá khỏi hệ thống.')
                continue
            if not hasattr(doc, '_sign_payload'):
                rec.is_valid = False
                rec.invalid_reason = _(
                    'Model %s không khai nội dung chịu trách nhiệm để đối '
                    'chiếu.') % rec.res_model
                continue
            if rec._bam(doc._sign_payload()) == rec.doc_hash:
                rec.is_valid = True
                rec.invalid_reason = False
            else:
                rec.is_valid = False
                rec.invalid_reason = _(
                    'Nội dung chứng từ đã thay đổi sau khi ký lúc %s.'
                ) % fields.Datetime.to_string(rec.signed_on)
