# -*- coding: utf-8 -*-
"""Doc Template — mẫu tài liệu Word (.docx) mail-merge."""
from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

# Model đích có thể sinh tài liệu. Chỉ hiện model thật sự có trong
# registry (module tương ứng đã cài) — re_doc là module community nên
# không phụ thuộc cứng vào bộ _sales.
CANDIDATE_MODELS = [
    ('re.sale.contract', 'Hợp đồng mua bán'),
    ('re.sale.deposit', 'Đặt cọc'),
    ('re.sale.addendum', 'Phụ lục hợp đồng'),
    ('re.sale.booking', 'Phiếu giữ chỗ'),
    ('re.sale.receipt', 'Phiếu thu'),
    ('re.sale.transfer', 'Chuyển nhượng'),
    ('re.sale.liquidation', 'Thanh lý hợp đồng'),
    ('re.sale.termination', 'Chấm dứt hợp đồng'),
    ('re.sale.handover', 'Biên bản bàn giao'),
]


class ReDocTemplate(models.Model):
    _name = 're.doc.template'
    _description = 'Mẫu tài liệu (Word mail-merge)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, name'

    sequence = fields.Integer(default=10)
    name = fields.Char(string='Tên mẫu', required=True, translate=True,
                       tracking=True)
    description = fields.Text(string='Mô tả', translate=True)
    target_model = fields.Selection(
        selection='_selection_target_model', string='Áp dụng cho',
        required=True, tracking=True,
        help='Loại hồ sơ mà mẫu này dùng để in.')
    active = fields.Boolean(default=True)
    docx_file = fields.Binary(
        string='Tệp Word (.docx)', attachment=True,
        help='File Word chứa placeholder Jinja2, ví dụ '
             '{{ record.partner_id.name }}')
    docx_filename = fields.Char(string='Tên tệp', tracking=True)
    output_pdf = fields.Boolean(
        string='Kết xuất PDF', default=False,
        help='Cần LibreOffice trong container Odoo. Chưa có thì hệ '
             'thống tự trả về .docx.')
    placeholder_help = fields.Html(
        string='Placeholder có sẵn', compute='_compute_placeholder_help',
        sanitize=False)

    @api.model
    def _selection_target_model(self):
        return [(m, label) for m, label in CANDIDATE_MODELS
                if m in self.env]

    @api.constrains('docx_filename')
    def _check_docx_extension(self):
        for tpl in self:
            if tpl.docx_filename and not tpl.docx_filename.lower().endswith(
                    '.docx'):
                raise ValidationError(_(
                    'Tệp mẫu phải là định dạng Word .docx (đang là "%s").')
                    % tpl.docx_filename)

    @api.depends('target_model')
    def _compute_placeholder_help(self):
        engine = self.env['re.doc.engine']
        for tpl in self:
            if not tpl.target_model:
                tpl.placeholder_help = Markup(
                    '<p class="text-muted">Chọn loại hồ sơ để xem danh '
                    'sách placeholder dùng được.</p>')
                continue
            parts = [Markup(
                '<div class="alert alert-info" role="status">'
                '<b>Cách dùng:</b> mở tệp Word, gõ đúng đoạn mã bên dưới '
                'vào chỗ cần điền. Với bảng nhiều dòng (lịch thanh toán, '
                'đồng sở hữu) đặt <code>{%tr for ... %}</code> ở ô đầu của '
                'dòng bảng và <code>{%tr endfor %}</code> ở dòng kế tiếp.'
                '</div>')]
            for group_name, rows in engine.curated_groups(tpl.target_model):
                parts.append(Markup(
                    '<h5 class="mt-3 mb-1">%s</h5>'
                    '<table class="table table-sm table-bordered">'
                    '<tbody>') % group_name)
                for label, snippet in rows:
                    parts.append(Markup(
                        '<tr><td style="width:38%%">%s</td>'
                        '<td><code>%s</code></td></tr>') % (label, snippet))
                parts.append(Markup('</tbody></table>'))
            tpl.placeholder_help = Markup('').join(parts)

    def action_open_render_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Tạo tài liệu'),
            'res_model': 're.doc.render.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_template_id': self.id,
                'default_target_model': self.target_model,
            },
        }
