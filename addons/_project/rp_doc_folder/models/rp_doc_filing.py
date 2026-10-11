# -*- coding: utf-8 -*-
"""Nộp hồ sơ của một SỔ vào đúng thư mục dự án của nó.

Cây thư mục đã khai mỗi thư mục là bãi đáp của sổ nào (``tool_model_id``),
nhưng trước đây đó mới chỉ là một lời khai: không có đường nào đưa tệp từ
một biên bản nghiệm thu, một phát sinh hay một bảo lãnh vào đúng thư mục
ấy. Người dùng chỉ còn cái kẹp giấy của khung trò chuyện, mà tệp thả vào
đó thì thư mục lẫn SharePoint đều không biết — nên thư mục `06.3 Quantity
acceptance` rỗng vĩnh viễn trong khi hồ sơ vẫn đang về đều.

Mixin này là đường đó, và cố ý làm **một lần dùng chung cho mọi sổ**: chỗ
hở giống hệt nhau ở cả 19 thư mục có sổ, vá riêng cho nghiệm thu thì mười
tám chỗ còn lại vẫn hở.

Giữ nguyên nguyên tắc của ``rp.doc.file``: **tệp nằm trên SharePoint,
Odoo chỉ giữ con trỏ.** Nộp xong là gỡ bản trong Odoo, để không bao giờ
phải trả lời câu "ai sửa bản nào thì bản nào đúng".
"""
import base64

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class RpDocFiling(models.AbstractModel):
    _name = 'rp.doc.filing'
    _description = 'Nộp hồ sơ vào thư mục dự án'

    # KHÔNG khai Many2many ir.attachment ở đây. Mixin dùng chung mà khai
    # m2m thì mọi model kế thừa đều sinh bảng quan hệ theo cùng một công
    # thức tên; sổ nào SẴN CÓ một m2m ir.attachment khác (rp.document.
    # revision.attachment_ids) là trùng tên bảng và registry chết hẳn:
    # "Many2many fields ... use the same table and columns". Sổ nào cần
    # hộp thả tệp riêng thì tự khai, kèm relation= tường minh.
    doc_folder_id = fields.Many2one(
        'rp.doc.folder', string='Thư mục hồ sơ',
        compute='_compute_doc_folder',
        help='Thư mục trong cây hồ sơ dự án đã khai sổ này là nguồn.')
    doc_folder_path = fields.Char(
        string='Nộp vào', compute='_compute_doc_folder')
    doc_file_ids = fields.Many2many(
        'rp.doc.file', string='Hồ sơ đã nộp',
        compute='_compute_doc_files')
    doc_file_count = fields.Integer(
        string='Số hồ sơ đã nộp', compute='_compute_doc_files')

    # ------------------------------------------------------------------
    def _rp_doc_project(self):
        """Dự án của bản ghi này. Sổ nào để dự án ở tên khác thì đè lại."""
        self.ensure_one()
        return self.project_id if 'project_id' in self._fields else False

    def _rp_doc_folder_model(self):
        """Model mà THƯ MỤC khai là sổ phụ trách.

        Thường trùng chính nó, nhưng không phải lúc nào cũng vậy: hồ sơ
        kỹ thuật nộp theo từng LẦN TRÌNH (``rp.document.revision``) —
        tệp thuộc Rev nào là chuyện cốt lõi của sổ trình duyệt — trong
        khi thư mục chỉ khai sổ cha ``rp.document``.
        """
        return self._name

    def _rp_doc_nguon_tep(self):
        """Tệp sẽ đem nộp. Sổ nào đã có sẵn ô đính kèm thì trỏ vào đó."""
        self.ensure_one()
        return self.doc_pending_ids \
            if 'doc_pending_ids' in self._fields \
            else self.env['ir.attachment']

    def _rp_doc_ten_nguon(self):
        """Tên ghi vào cột "Nộp từ" của tệp.

        Mặc định là display_name, nhưng sổ con thì phải đè: một lần
        trình tên "Rev 0" đứng trong thư mục chung của cả dự án thì
        chẳng chỉ ra được nó là Rev 0 của hồ sơ nào.
        """
        self.ensure_one()
        return self.display_name

    def _rp_doc_ten_tep(self, att):
        """Tên tệp khi nằm trên SharePoint.

        Mặc định giữ nguyên. Sổ nào nộp nhiều tệp cùng loại thì nên đè
        lại: một thư mục đầy "ban-ve.pdf", "ban-ve(1).pdf" thì mở ra
        không biết cái nào của hồ sơ nào, Rev mấy.
        """
        return att.name

    @api.depends_context('uid')
    def _compute_doc_folder(self):
        Folder = self.env['rp.doc.folder']
        for rec in self:
            p = rec._rp_doc_project()
            f = Folder.search(
                [('project_id', '=', p.id),
                 ('tool_model_id.model', '=',
                  rec._rp_doc_folder_model())], limit=1) if p \
                else Folder.browse()
            rec.doc_folder_id = f
            rec.doc_folder_path = f.full_path or False

    def _compute_doc_files(self):
        File = self.env['rp.doc.file']
        for rec in self:
            f = File.search([('source_model', '=', rec._name),
                             ('source_id', '=', rec.id or 0)])
            rec.doc_file_ids = f
            rec.doc_file_count = len(f)

    # ------------------------------------------------------------------
    def action_nop_ho_so(self):
        """Đưa tệp đang chờ lên SharePoint đúng thư mục, rồi gỡ khỏi Odoo."""
        self.ensure_one()
        tep = self._rp_doc_nguon_tep()
        if not tep:
            raise UserError(_('Chưa có tệp nào để nộp.'))
        folder = self.doc_folder_id
        if not folder:
            raise UserError(_(
                'Cây hồ sơ của dự án chưa có thư mục nào khai sổ "%s" là '
                'nguồn. Vào Dự án → Hồ sơ, mở thư mục cần dùng rồi chọn sổ '
                'đó ở ô "Sổ phụ trách".',
                self.env['ir.model']._get(self._rp_doc_folder_model()).name
                or self._rp_doc_folder_model()))
        if not folder.sp_item_id:
            raise UserError(_(
                'Thư mục "%s" chưa có trên SharePoint — mở form dự án bấm '
                '"Đẩy lên SharePoint" trước.', folder.display_name))

        # Người dùng đã chứng minh thẩm quyền bằng việc được GHI bản ghi
        # này; con trỏ tệp thì phải sudo vì rp.doc.file để quyền tạo cho
        # quản lý, còn người nộp hồ sơ thường chỉ là người dùng thường.
        self.check_access('write')
        kho = folder.sudo()
        cfg = kho._cfg()
        tok = cfg._token()
        File = self.env['rp.doc.file'].sudo()
        n = 0
        for a in tep:
            if not a.datas:
                continue
            ten = self._rp_doc_ten_tep(a)
            kho._day_mot_tep(cfg, tok, ten, base64.b64decode(a.datas))
            # Gắn ngược con trỏ về bản ghi nguồn, để mở thư mục là biết
            # tệp này thuộc biên bản nào — không có nó thì thư mục lại
            # thành một đống tệp rời không truy được nguồn.
            # Tìm theo TÊN ĐÃ CHUẨN HOÁ của SharePoint, không theo tên gốc:
            # _ten_sp bỏ ký tự Graph không nhận, nên hai tên lệch nhau.
            ptr = File.search([('folder_id', '=', kho.id),
                               ('name', '=', cfg._ten_sp(ten))], limit=1)
            if ptr:
                ptr.write({'source_model': self._name,
                           'source_id': self.id,
                           'source_name': self._rp_doc_ten_nguon()})
            n += 1
        # Gỡ SAU khi đã lên hết: lỗi giữa chừng thì giao dịch quay lui và
        # tệp vẫn còn trong Odoo, không mất.
        tep.unlink()
        self.invalidate_recordset(['doc_file_ids', 'doc_file_count'])
        if hasattr(self, 'message_post'):
            self.message_post(body=_(
                'Đã nộp %(n)s hồ sơ vào thư mục %(t)s trên SharePoint.',
                n=n, t=folder.full_path))
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {'type': 'success', 'message': _(
                'Đã nộp %(n)s tệp vào %(t)s.', n=n, t=folder.full_path)},
        }

    def action_mo_thu_muc(self):
        self.ensure_one()
        if not self.doc_folder_id:
            raise UserError(_('Sổ này chưa được thư mục nào nhận.'))
        return {
            'type': 'ir.actions.act_window', 'res_model': 'rp.doc.folder',
            'res_id': self.doc_folder_id.id, 'view_mode': 'form',
        }
