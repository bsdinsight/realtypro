# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ReProject(models.Model):
    _inherit = 're.project'

    doc_folder_ids = fields.One2many(
        'rp.doc.folder', 'project_id', string='Thư mục hồ sơ')
    doc_folder_count = fields.Integer(
        string='Số thư mục', compute='_compute_doc_folder')
    doc_file_count = fields.Integer(
        string='Số tệp', compute='_compute_doc_folder')
    doc_missing_count = fields.Integer(
        string='Thư mục bắt buộc còn rỗng', compute='_compute_doc_folder')

    @api.depends('doc_folder_ids.file_count',
                 'doc_folder_ids.is_empty_required')
    def _compute_doc_folder(self):
        for p in self:
            tm = p.doc_folder_ids
            p.doc_folder_count = len(tm)
            p.doc_file_count = sum(tm.mapped('file_count'))
            p.doc_missing_count = len(tm.filtered('is_empty_required'))

    def rp_tao_thu_muc(self, template_id=False, cap_nhat=False):
        """Dựng bộ thư mục chuẩn cho dự án.

        Chạy lại được bao nhiêu lần cũng được: thư mục đã có thì bỏ qua
        theo mã, chỉ thêm cái còn thiếu. Nhờ vậy khi bộ chuẩn được bổ
        sung về sau, dự án đang chạy vẫn nhận được thư mục mới mà không
        mất gì — thao tác "dựng lại" không bao giờ được xoá hồ sơ.

        ``cap_nhat`` đồng bộ thêm tên, sổ phụ trách và dấu bắt buộc của
        thư mục đã có, dùng khi bộ chuẩn được sửa. Nó vẫn không đụng tới
        tệp, không đụng neo SharePoint, và không xoá thư mục nào — kể cả
        thư mục người dùng tự thêm ngoài bộ chuẩn.
        """
        T = self.env['rp.doc.folder.template']
        F = self.env['rp.doc.folder']
        khuon = (T.browse(template_id) if template_id
                 else T.search([], order='sequence, id', limit=1))
        if not khuon:
            raise UserError(_('Chưa khai bộ thư mục chuẩn nào.'))
        tong = 0
        for p in self:
            co = {f.code: f for f in p.doc_folder_ids}
            # Cha phải tạo trước con — sắp theo độ sâu của mã.
            dong = khuon.line_ids.sorted(
                lambda l: (len((l.code or '').split('.')), l.code or ''))
            for l in dong:
                if l.code in co:
                    if cap_nhat:
                        co[l.code].write({
                            'name': l.name,
                            'tool_model_id': l.tool_model_id.id or False,
                            'is_required': l.is_required,
                            'note': l.note,
                        })
                    continue
                cha = co.get(l.parent_id.code) if l.parent_id else False
                co[l.code] = F.create({
                    'project_id': p.id,
                    'code': l.code,
                    'name': l.name,
                    'sequence': l.sequence,
                    'parent_id': cha.id if cha else False,
                    'tool_model_id': l.tool_model_id.id or False,
                    'is_required': l.is_required,
                    'note': l.note,
                    'template_id': khuon.id,
                })
                tong += 1
        return tong

    def action_tao_thu_muc(self):
        n = self.rp_tao_thu_muc()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success' if n else 'warning',
                'message': (_('Đã dựng %s thư mục.', n) if n else
                            _('Không có thư mục nào phải thêm — bộ thư '
                              'mục đã đầy đủ.')),
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }

    def action_day_sharepoint(self):
        """Dựng cây thư mục của dự án lên SharePoint."""
        self.ensure_one()
        if not self.doc_folder_ids:
            raise UserError(_('Dựng bộ thư mục chuẩn trước đã.'))
        n = self.env['rp.sharepoint.config']._lay().rp_dung_cay(self)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': (_('Đã tạo %s thư mục trên SharePoint.', n)
                            if n else
                            _('Không có thư mục nào phải tạo — SharePoint '
                              'đã khớp.')),
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }

    def action_lam_moi_sharepoint(self):
        """Đọc ngược toàn bộ cây từ SharePoint.

        Phần lớn hồ sơ đi vào qua Teams hay File Explorer chứ không qua
        Odoo. Không đọc ngược thì cột "thư mục bắt buộc còn rỗng" nói
        dối, mà đó lại là cột đáng tin nhất của màn hình này.
        """
        self.ensure_one()
        return self.doc_folder_ids.action_lam_moi()

    def action_mo_thu_muc(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Thư mục hồ sơ — %s', self.display_name),
            'res_model': 'rp.doc.folder',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }
