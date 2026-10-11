# -*- coding: utf-8 -*-
"""Bản PDF đã ký số của một chứng từ.

Giữ cả file: chữ ký số nằm TRONG file, nên file chính là bằng chứng.
Mất file thì chữ ký cũng không còn gì để kiểm — khác hẳn ``re.signature``
nơi bằng chứng là mã băm trong cơ sở dữ liệu.
"""
from odoo import _, api, fields, models


class ReCaSignature(models.Model):
    _name = 're.ca.signature'
    _description = 'Bản PDF đã ký số'
    _order = 'create_date desc, id desc'
    _rec_name = 'file_name'

    res_model = fields.Char(string='Model', required=True, index=True)
    res_id = fields.Integer(string='Bản ghi', required=True, index=True)
    res_name = fields.Char(string='Chứng từ', compute='_compute_res_name')

    file_name = fields.Char(string='Tên tệp', required=True)
    file_data = fields.Binary(string='PDF đã ký', required=True,
                              attachment=True)
    provider = fields.Selection(
        [('test', 'Chứng thư thử'),
         ('smartca', 'Ký số từ xa (CA)'),
         ('token', 'Token USB')],
        string='Đường ký', required=True, default='test')
    signer_name = fields.Char(string='Người ký', required=True)
    signed_on = fields.Datetime(
        string='Ký lúc', required=True, default=fields.Datetime.now,
        readonly=True)
    signed_uid = fields.Many2one(
        'res.users', string='Tài khoản ký', readonly=True,
        default=lambda self: self.env.user)
    verify_note = fields.Text(string='Kết quả kiểm tra', readonly=True)

    @api.depends('res_model', 'res_id')
    def _compute_res_name(self):
        for rec in self:
            if rec.res_model in self.env:
                doc = self.env[rec.res_model].browse(rec.res_id).exists()
                rec.res_name = doc.display_name if doc else _('(đã xoá)')
            else:
                rec.res_name = _('(đã xoá)')

    def action_kiem_tra(self):
        """Đọc lại chữ ký trong chính file — không tin cái đã ghi lúc ký.

        Ghi chú lúc ký chỉ nói được tình trạng TẠI LÚC ĐÓ. Câu hỏi thật
        là "bây giờ file này còn nguyên không", và chỉ có cách mở file
        ra đọc mới trả lời được.
        """
        import base64
        self.ensure_one()
        S = self.env['re.ca.service']
        ds = S.read_signatures(base64.b64decode(self.file_data))
        if not ds:
            self.verify_note = _('Không tìm thấy chữ ký số nào trong tệp.')
        else:
            dong = []
            for d in ds:
                if d.get('error'):
                    dong.append(_('Lỗi đọc chữ ký: %s') % d['error'])
                    continue
                dong.append(_(
                    'Người ký: %(n)s\nKý lúc: %(t)s\n'
                    'Tài liệu còn nguyên vẹn: %(i)s\n'
                    'Chứng thư được tin cậy: %(tr)s\n%(s)s',
                    n=d['name'], t=d['signed_on'],
                    i=_('có') if d['intact'] else _('KHÔNG'),
                    tr=_('có') if d['trusted'] else _(
                        'chưa — chứng thư không do tổ chức chứng thực cấp'),
                    s=d['summary']))
            self.verify_note = '\n\n'.join(dong)
        return {
            'type': 'ir.actions.act_window', 'res_model': self._name,
            'res_id': self.id, 'view_mode': 'form', 'target': 'new',
        }
