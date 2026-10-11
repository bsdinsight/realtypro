# -*- coding: utf-8 -*-
"""Mixin cho mọi chứng từ ký được.

Model nào muốn ký chỉ cần thêm ``re.signable`` vào ``_inherit`` rồi viết
``_sign_payload()``. Viết cái đó là việc PHẢI nghĩ, không phải thủ tục:
nó quyết định chữ ký bảo chứng cho những gì. Bỏ sót một trường quyết
định (số ngày gia hạn, số tiền) thì sửa trường đó xong chữ ký vẫn báo
hợp lệ — tệ hơn là không có chữ ký, vì giờ có cả một tấm ảnh nói rằng
đã duyệt.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ReSignable(models.AbstractModel):
    _name = 're.signable'
    _description = 'Chứng từ ký được'

    signature_ids = fields.One2many(
        're.signature', 'res_id', string='Chữ ký',
        domain=lambda self: [('res_model', '=', self._name)])
    sign_count = fields.Integer(
        string='Số chữ ký', compute='_compute_sign_state')
    sign_state = fields.Selection(
        [('unsigned', 'Chưa ký'),
         ('signed', 'Đã ký'),
         ('broken', 'Đã sửa sau khi ký')],
        string='Tình trạng ký', compute='_compute_sign_state')
    sign_warning = fields.Char(
        string='Cảnh báo chữ ký', compute='_compute_sign_state')

    # ------------------------------------------------------------------
    def _sign_payload(self):
        """Chuỗi chuẩn tắc của phần NỘI DUNG CHỊU TRÁCH NHIỆM.

        Bắt buộc ghi đè. Không ghi đè thì chữ ký không bảo chứng gì, nên
        ở đây báo lỗi thẳng chứ không trả về một giá trị mặc định nghe
        có vẻ an toàn.
        """
        raise NotImplementedError(
            'Model %s kế thừa re.signable thì phải khai _sign_payload()'
            % self._name)

    def _compute_sign_state(self):
        for rec in self:
            chu_ky = rec.signature_ids
            rec.sign_count = len(chu_ky)
            if not chu_ky:
                rec.sign_state = 'unsigned'
                rec.sign_warning = False
                continue
            hong = chu_ky.filtered(lambda s: not s.is_valid)
            if hong:
                rec.sign_state = 'broken'
                rec.sign_warning = _(
                    '%(n)s trên %(t)s chữ ký không còn hợp lệ — nội dung '
                    'chứng từ đã bị sửa sau khi ký. Phải huỷ chữ ký cũ và '
                    'ký lại thì mới có giá trị.',
                    n=len(hong), t=len(chu_ky))
            else:
                rec.sign_state = 'signed'
                rec.sign_warning = False

    # ------------------------------------------------------------------
    def action_open_sign_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Ký duyệt — %s') % self.display_name,
            'res_model': 're.sign.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_res_model': self._name,
                'default_res_id': self.id,
            },
        }

    def action_view_signatures(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Chữ ký — %s') % self.display_name,
            'res_model': 're.signature',
            'view_mode': 'list,form',
            'domain': [('res_model', '=', self._name),
                       ('res_id', '=', self.id)],
            'target': 'current',
        }

    def action_huy_chu_ky(self):
        """Huỷ toàn bộ chữ ký của chứng từ này.

        Sửa nội dung rồi ký lại là chuyện bình thường; cái không bình
        thường là để chữ ký cũ nằm lại cạnh nội dung mới.
        """
        self.ensure_one()
        if not self.signature_ids:
            raise UserError(_('Chứng từ này chưa có chữ ký nào.'))
        n = len(self.signature_ids)
        self.signature_ids.unlink()
        if hasattr(self, 'message_post'):
            self.message_post(body=_('Đã huỷ %s chữ ký.') % n)
        return True
