# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class RpDocFolder(models.Model):
    """Thư mục thật của một dự án, dựng từ khuôn."""
    _name = 'rp.doc.folder'
    _description = 'Thư mục hồ sơ dự án'
    _parent_name = 'parent_id'
    _parent_store = True
    _order = 'project_id, code, sequence, id'
    _rec_name = 'display_name'

    project_id = fields.Many2one(
        're.project', string='Dự án', required=True, ondelete='cascade',
        index=True)
    code = fields.Char(string='Mã', required=True, index=True)
    name = fields.Char(string='Tên thư mục', required=True)
    sequence = fields.Integer(default=10)
    parent_id = fields.Many2one(
        'rp.doc.folder', string='Thư mục cha', ondelete='cascade',
        index=True)
    child_ids = fields.One2many(
        'rp.doc.folder', 'parent_id', string='Thư mục con')
    parent_path = fields.Char(index=True)
    full_path = fields.Char(
        string='Đường dẫn', compute='_compute_full_path', store=True,
        recursive=True,
        help='Đường dẫn tương đối, dùng luôn làm đường dẫn trên '
             'SharePoint để hai bên không lệch nhau.')
    tool_model_id = fields.Many2one(
        'ir.model', string='Sổ phụ trách', ondelete='set null')
    tool_name = fields.Char(
        string='Tên sổ', compute='_compute_tool', store=True)
    is_required = fields.Boolean(string='Bắt buộc có hồ sơ')
    note = fields.Text(string='Đưa gì vào đây')
    template_id = fields.Many2one(
        'rp.doc.folder.template', string='Dựng từ bộ')

    file_count = fields.Integer(
        string='Số tệp', compute='_compute_file_count', store=True)
    file_count_total = fields.Integer(
        string='Số tệp (gồm thư mục con)', compute='_compute_file_count',
        store=True, recursive=True)
    is_empty_required = fields.Boolean(
        string='Bắt buộc nhưng còn rỗng', compute='_compute_file_count',
        store=True, recursive=True,
        help='Thư mục đánh dấu bắt buộc mà chưa có tệp nào — đây là cột '
             'đáng nhìn nhất trước ngày bàn giao.')

    # --- neo sang SharePoint (điền khi đã đấu nối)
    sp_drive_id = fields.Char(string='SharePoint drive', copy=False)
    sp_item_id = fields.Char(string='SharePoint item', copy=False)
    sp_url = fields.Char(string='Mở trên SharePoint', copy=False)
    sp_synced_on = fields.Datetime(string='Lần đồng bộ cuối', copy=False)

    _uniq_ma = models.Constraint(
        'UNIQUE(project_id, code)',
        'Mỗi dự án không được có hai thư mục trùng mã.')

    @api.depends('code', 'name', 'parent_id.full_path')
    def _compute_full_path(self):
        for f in self:
            ten = '%s %s' % (f.code or '', f.name or '')
            f.full_path = ('%s/%s' % (f.parent_id.full_path, ten.strip())
                           if f.parent_id else ten.strip())

    @api.depends('full_path')
    def _compute_display_name(self):
        for f in self:
            f.display_name = f.full_path or f.name or ''

    @api.depends('tool_model_id')
    def _compute_tool(self):
        for f in self:
            f.tool_name = f.tool_model_id.name or False

    def action_mo_so(self):
        """Nhảy thẳng sang sổ phụ trách, lọc sẵn theo dự án.

        Phân vai "thư mục giữ file, sổ giữ ý nghĩa" chỉ dùng được khi đi
        từ thư mục sang sổ mất đúng một cú bấm; bắt người ta tự mò lại
        trong thực đơn thì họ quay về thả hồ sơ rời vào thư mục.
        """
        self.ensure_one()
        mo = self.tool_model_id.model
        if not mo:
            raise UserError(_('Thư mục này chưa khai sổ phụ trách.'))
        if mo not in self.env:
            raise UserError(_(
                'Sổ "%s" thuộc một module hiện không cài.', mo))
        Model = self.env[mo]
        linh = 'project_id' in Model._fields
        return {
            'type': 'ir.actions.act_window',
            'name': self.tool_model_id.name,
            'res_model': mo,
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.project_id.id)] if linh
            else [],
            'context': {'default_project_id': self.project_id.id} if linh
            else {},
        }
