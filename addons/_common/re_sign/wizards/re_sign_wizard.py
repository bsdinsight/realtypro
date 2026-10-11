# -*- coding: utf-8 -*-
"""Hộp thoại ký: xem lại nội dung sắp bảo chứng, rồi mới ký."""
from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.re_sign.models.re_signature import VAI


class ReSignWizard(models.TransientModel):
    _name = 're.sign.wizard'
    _description = 'Ký duyệt chứng từ'

    res_model = fields.Char(required=True)
    res_id = fields.Integer(required=True)
    doc_name = fields.Char(string='Chứng từ', compute='_compute_doc')
    payload_preview = fields.Text(
        string='Nội dung chữ ký bảo chứng', compute='_compute_doc',
        help='Đúng những dòng này được băm vào chữ ký. Sửa bất kỳ dòng '
             'nào sau khi ký thì chữ ký tự báo không còn hợp lệ.')

    role = fields.Selection(VAI, string='Ký với vai', required=True,
                            default='owner')
    signer_name = fields.Char(
        string='Họ tên người ký', required=True,
        default=lambda self: self.env.user.name)
    signer_title = fields.Char(string='Chức danh')
    partner_id = fields.Many2one('res.partner', string='Thuộc đơn vị')
    signature = fields.Binary(string='Chữ ký', required=True)

    # ------------------------------------------------------------------
    def _doc(self):
        if not self.res_model or self.res_model not in self.env:
            return None
        return self.env[self.res_model].browse(self.res_id).exists()

    @api.depends('res_model', 'res_id')
    def _compute_doc(self):
        for rec in self:
            doc = rec._doc()
            rec.doc_name = doc.display_name if doc else _('(không tìm thấy)')
            if doc and hasattr(doc, '_sign_payload'):
                rec.payload_preview = doc._sign_payload()
            else:
                rec.payload_preview = False

    def action_ky(self):
        self.ensure_one()
        doc = self._doc()
        if not doc:
            raise UserError(_('Chứng từ không còn tồn tại.'))
        if not hasattr(doc, '_sign_payload'):
            raise UserError(_(
                'Model %s chưa khai nội dung chịu trách nhiệm nên không ký '
                'được — ký lên một chứng từ không băm được nội dung thì '
                'chữ ký chẳng bảo chứng điều gì.') % self.res_model)

        Sig = self.env['re.signature']
        # IP lấy từ request, có thể không có (cron, test, gọi từ shell).
        ip = False
        req = getattr(self.env, 'request', None) or None
        try:
            from odoo.http import request as _rq
            if _rq and _rq.httprequest:
                ip = _rq.httprequest.remote_addr
        except Exception:
            ip = False

        chu_ky = Sig.create({
            'res_model': self.res_model,
            'res_id': self.res_id,
            'role': self.role,
            'signer_name': self.signer_name,
            'signer_title': self.signer_title,
            'partner_id': self.partner_id.id,
            'signature': self.signature,
            'signed_ip': ip,
            'doc_hash': Sig._bam(doc._sign_payload()),
        })
        if hasattr(doc, 'message_post'):
            doc.message_post(body=_(
                '%(ten)s (%(vai)s) đã ký duyệt.',
                ten=self.signer_name,
                vai=dict(VAI).get(self.role, self.role)))
        return {'type': 'ir.actions.act_window_close'}
