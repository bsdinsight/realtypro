# -*- coding: utf-8 -*-
from odoo import _, api, fields, models


class RpDocFolderTemplate(models.Model):
    """Bộ thư mục chuẩn — cái khuôn, không phải thư mục thật.

    Một tổ chức có vài loại dự án với bộ hồ sơ khác hẳn nhau: nhà máy
    điện không có "căn hộ mẫu", chung cư không có "thử nghiệm hoà lưới".
    Nên khuôn phải nhiều bộ, chọn khi dựng, chứ không phải một cây cứng
    nhét cho mọi dự án rồi ai cũng có mười thư mục rỗng vĩnh viễn.
    """
    _name = 'rp.doc.folder.template'
    _description = 'Bộ thư mục hồ sơ chuẩn'
    _order = 'sequence, id'

    name = fields.Char(string='Tên bộ', required=True, translate=True)
    code = fields.Char(string='Mã')
    sequence = fields.Integer(default=10)
    note = fields.Text(string='Phạm vi áp dụng')
    line_ids = fields.One2many(
        'rp.doc.folder.template.line', 'template_id', string='Thư mục')
    line_count = fields.Integer(compute='_compute_line_count')
    active = fields.Boolean(default=True)

    @api.depends('line_ids')
    def _compute_line_count(self):
        for t in self:
            t.line_count = len(t.line_ids)

    def action_ap_vao_du_an(self):
        """Áp bộ chuẩn đã sửa vào mọi dự án đã dựng từ nó.

        Dự án đang chạy mới là nơi bộ chuẩn phải đúng. Thêm thư mục còn
        thiếu và đồng bộ lại tên / sổ phụ trách / dấu bắt buộc — không
        xoá thư mục nào và không đụng vào tệp.
        """
        self.ensure_one()
        da = self.env['rp.doc.folder'].search(
            [('template_id', '=', self.id)]).mapped('project_id')
        them = da.rp_tao_thu_muc(template_id=self.id, cap_nhat=True)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': _('Đã áp vào %(n)s dự án — thêm %(t)s thư mục, '
                             'đồng bộ lại phần còn lại.',
                             n=len(da), t=them),
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }


class RpDocFolderTemplateLine(models.Model):
    _name = 'rp.doc.folder.template.line'
    _description = 'Thư mục trong bộ chuẩn'
    _parent_name = 'parent_id'
    _parent_store = True
    _order = 'code, sequence, id'

    template_id = fields.Many2one(
        'rp.doc.folder.template', string='Bộ thư mục', required=True,
        ondelete='cascade', index=True)
    code = fields.Char(string='Mã', required=True)
    name = fields.Char(string='Tên thư mục', required=True, translate=True)
    sequence = fields.Integer(default=10)
    parent_id = fields.Many2one(
        'rp.doc.folder.template.line', string='Thư mục cha',
        ondelete='cascade', index=True)
    child_ids = fields.One2many(
        'rp.doc.folder.template.line', 'parent_id', string='Thư mục con')
    parent_path = fields.Char(index=True)
    # Thư mục nào đã có SỔ riêng trong hệ thống thì không phải chỗ thả
    # file rời — nó là bãi đáp file của sổ đó. Khai ra để màn hình nhảy
    # thẳng sang sổ, tránh đúng cái bẫy Procore cảnh báo: tạo thư mục
    # cho thứ đã có công cụ là lập tức có hai nguồn sự thật.
    tool_model_id = fields.Many2one(
        'ir.model', string='Sổ phụ trách',
        ondelete='set null',
        help='Hồ sơ loại này do sổ nào quản lý. Để trống nghĩa là thư '
             'mục này là chỗ lưu file thuần tuý, không có sổ nào theo.')
    is_required = fields.Boolean(
        string='Bắt buộc có hồ sơ', default=False,
        help='Đánh dấu các thư mục mà rỗng là có vấn đề: hồ sơ hoàn '
             'công, tài liệu vận hành, giấy phép. Dùng để soát trước '
             'bàn giao.')
    note = fields.Text(string='Đưa gì vào đây')
