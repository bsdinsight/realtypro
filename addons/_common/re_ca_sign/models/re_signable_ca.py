# -*- coding: utf-8 -*-
"""Gắn khả năng ký số vào mọi chứng từ đã kế thừa ``re.signable``."""
import base64

from odoo import _, fields, models
from odoo.exceptions import UserError


class ReSignableCa(models.AbstractModel):
    _inherit = 're.signable'

    ca_signature_ids = fields.One2many(
        're.ca.signature', 'res_id', string='Bản PDF đã ký số',
        domain=lambda self: [('res_model', '=', self._name)])
    ca_sign_count = fields.Integer(
        string='Số bản ký số', compute='_compute_ca_sign_count')

    def _compute_ca_sign_count(self):
        for rec in self:
            rec.ca_sign_count = len(rec.ca_signature_ids)

    # ------------------------------------------------------------------
    def _ca_report_ref(self):
        """xmlid của mẫu in dùng làm tài liệu ký.

        Mỗi chứng từ tự khai. Không có mặc định: ký số là ký lên MỘT TỜ
        GIẤY cụ thể, không phải lên một bản ghi — chọn nhầm mẫu in là ký
        nhầm nội dung.
        """
        raise NotImplementedError(
            'Model %s phải khai _ca_report_ref() thì mới ký số được'
            % self._name)

    def _ca_file_name(self):
        self.ensure_one()
        ten = (self.display_name or self._name).replace('/', '-')
        return '%s - da ky so.pdf' % ten[:80]

    def _ca_reason(self):
        return _('Phê duyệt trên hệ thống EPCOne')

    # ------------------------------------------------------------------
    def action_ky_so(self):
        self.ensure_one()
        S = self.env['re.ca.service']
        S._require_pyhanko()

        report = self.env.ref(self._ca_report_ref(), raise_if_not_found=False)
        if not report:
            raise UserError(_(
                'Chưa có mẫu in cho chứng từ này nên chưa ký số được — ký '
                'số là ký lên một tờ giấy cụ thể.'))
        pdf, _ext = report._render_qweb_pdf(report.report_name, res_ids=self.ids)

        ten_nguoi_ky = self.env.user.name
        da_ky = S.sign_pdf(
            pdf, signer_name=ten_nguoi_ky, reason=self._ca_reason(),
            doc_name=self.display_name)

        ban = self.env['re.ca.signature'].create({
            'res_model': self._name,
            'res_id': self.id,
            'file_name': self._ca_file_name(),
            'file_data': base64.b64encode(da_ky),
            'provider': S.get_provider(),
            'signer_name': ten_nguoi_ky,
        })
        ban.action_kiem_tra()
        if hasattr(self, 'message_post'):
            self.message_post(
                body=_('%s đã ký số bản PDF của chứng từ này.')
                % ten_nguoi_ky,
                attachments=[(ban.file_name, da_ky)])
        return {
            'type': 'ir.actions.act_window',
            'name': _('Bản PDF đã ký số'),
            'res_model': 're.ca.signature',
            'res_id': ban.id, 'view_mode': 'form', 'target': 'new',
        }

    def action_view_ca_signatures(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Bản PDF đã ký số — %s') % self.display_name,
            'res_model': 're.ca.signature',
            'view_mode': 'list,form',
            'domain': [('res_model', '=', self._name),
                       ('res_id', '=', self.id)],
        }
