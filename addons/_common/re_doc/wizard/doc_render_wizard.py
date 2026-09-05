# -*- coding: utf-8 -*-
"""Wizard: chọn mẫu → kết xuất tài liệu cho một hồ sơ."""
import base64

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ReDocRenderWizard(models.TransientModel):
    _name = 're.doc.render.wizard'
    _description = 'Tạo tài liệu từ mẫu'

    target_model = fields.Char(string='Loại hồ sơ', required=True)
    target_id = fields.Integer(string='Hồ sơ', required=True)
    target_name = fields.Char(
        string='Hồ sơ', compute='_compute_target_name')
    template_id = fields.Many2one(
        're.doc.template', string='Mẫu tài liệu', required=True,
        domain="[('target_model', '=', target_model), ('active', '=', True)]")
    attach_to_record = fields.Boolean(
        string='Lưu vào hồ sơ', default=True,
        help='Đính tài liệu vào hồ sơ và ghi vào nhật ký trao đổi.')
    output_filename = fields.Char(string='Tên tệp', readonly=True)
    output_file = fields.Binary(string='Tài liệu', readonly=True)

    @api.depends('target_model', 'target_id')
    def _compute_target_name(self):
        for wiz in self:
            name = ''
            if wiz.target_model and wiz.target_id:
                rec = self.env[wiz.target_model].browse(
                    wiz.target_id).exists()
                name = rec.display_name if rec else ''
            wiz.target_name = name

    def _get_record(self):
        self.ensure_one()
        if not self.target_model or not self.target_id:
            raise UserError(_('Chưa xác định được hồ sơ cần in.'))
        record = self.env[self.target_model].browse(self.target_id).exists()
        if not record:
            raise UserError(_('Hồ sơ không còn tồn tại.'))
        return record

    def action_render(self):
        self.ensure_one()
        record = self._get_record()
        content, filename = self.env['re.doc.engine'].render_template(
            self.template_id, record)
        data = base64.b64encode(content)

        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'datas': data,
            'res_model': record._name,
            'res_id': record.id,
            'mimetype': (
                'application/pdf' if filename.lower().endswith('.pdf')
                else 'application/vnd.openxmlformats-officedocument'
                     '.wordprocessingml.document'),
        })
        if self.attach_to_record and hasattr(record, 'message_post'):
            record.message_post(
                body=_('Đã tạo tài liệu từ mẫu "%s".') % self.template_id.name,
                attachment_ids=[attachment.id])
        self.write({'output_file': data, 'output_filename': filename})
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=true' % attachment.id,
            'target': 'self',
        }
