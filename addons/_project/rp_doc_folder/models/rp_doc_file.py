# -*- coding: utf-8 -*-
import base64
import logging

import requests

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Graph cho PUT thẳng tới 4 MB; lớn hơn phải mở phiên tải lên.
NGUONG_PUT = 4 * 1024 * 1024
TRAN = 250 * 1024 * 1024
TIMEOUT = 180


class RpDocFile(models.Model):
    """Một tệp NẰM TRÊN SharePoint, Odoo chỉ giữ con trỏ.

    Không giữ bản sao nhị phân trong Odoo. Giữ hai bản là lập tức có câu
    hỏi không trả lời được: ai sửa bản nào thì bản nào đúng. Tệp ở
    SharePoint, Odoo giữ tên, kích thước, ngày sửa và đường dẫn mở.

    Bảng này phải phản ánh được cả tệp người ta thả THẲNG vào SharePoint
    — đó mới là cách phần lớn hồ sơ đi vào, qua Teams hay File Explorer
    chứ không qua Odoo. Nếu Odoo chỉ biết tệp do chính nó đưa lên thì
    cột "thư mục bắt buộc còn rỗng" sẽ nói dối, mà đó lại là cột đáng
    tin nhất của màn hình này.
    """
    _name = 'rp.doc.file'
    _description = 'Tệp hồ sơ trên SharePoint'
    _order = 'folder_id, name'

    folder_id = fields.Many2one(
        'rp.doc.folder', string='Thư mục', required=True,
        ondelete='cascade', index=True)
    project_id = fields.Many2one(
        related='folder_id.project_id', store=True, index=True)
    name = fields.Char(string='Tên tệp', required=True)
    sp_item_id = fields.Char(string='SharePoint item', index=True)
    sp_url = fields.Char(string='Mở trên SharePoint')
    size = fields.Integer(string='Dung lượng (byte)')
    size_human = fields.Char(string='Dung lượng', compute='_compute_size')
    date_modified = fields.Datetime(string='Sửa lần cuối')
    modified_by = fields.Char(string='Người sửa')
    mimetype = fields.Char(string='Kiểu tệp')

    _uniq_item = models.Constraint(
        'UNIQUE(folder_id, sp_item_id)',
        'Một tệp SharePoint chỉ được ghi một lần trong thư mục.')

    @api.depends('size')
    def _compute_size(self):
        for t in self:
            n = float(t.size or 0)
            for dv in ('B', 'KB', 'MB', 'GB'):
                if n < 1024 or dv == 'GB':
                    t.size_human = '%.0f %s' % (n, dv) if dv == 'B' \
                        else '%.1f %s' % (n, dv)
                    break
                n /= 1024

    def action_mo(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_url', 'url': self.sp_url,
                'target': 'new'}


class RpDocFolderFiles(models.Model):
    _inherit = 'rp.doc.folder'

    file_ids = fields.One2many(
        'rp.doc.file', 'folder_id', string='Tệp trên SharePoint')
    # Hộp thả tệp. Tệp rơi vào đây chỉ nằm tạm: đưa lên SharePoint xong
    # là gỡ khỏi Odoo, để không bao giờ có hai bản của cùng một tệp.
    upload_ids = fields.Many2many(
        'ir.attachment', 'rp_doc_folder_upload_rel', 'folder_id',
        'attachment_id', string='Tệp chờ đưa lên')

    # ------------------------------------------------------------------
    def _cfg(self):
        c = self.env['rp.sharepoint.config']._lay()
        if c.state != 'ok' or not c.drive_id:
            raise UserError(_(
                'Chưa đấu nối SharePoint. Vào Cấu hình → SharePoint và '
                'bấm "Kiểm tra kết nối".'))
        return c

    def action_day_tep(self):
        """Đưa tệp đang chờ lên SharePoint rồi gỡ khỏi Odoo."""
        cfg = self._cfg()
        tok = cfg._token()
        n = 0
        for f in self:
            if not f.sp_item_id:
                raise UserError(_(
                    'Thư mục "%s" chưa có trên SharePoint — bấm "Đẩy lên '
                    'SharePoint" ở form dự án trước.', f.display_name))
            for a in f.upload_ids:
                f._day_mot_tep(cfg, tok, a.name, base64.b64decode(a.datas))
                n += 1
            # Gỡ SAU khi đã lên hết: lỗi giữa chừng thì giao dịch quay
            # lui và tệp vẫn còn trong Odoo, không mất.
            f.upload_ids.unlink()
        return self._bao(_('Đã đưa %s tệp lên SharePoint.', n) if n
                         else _('Không có tệp nào đang chờ.'))

    def _day_mot_tep(self, cfg, tok, ten, noi_dung):
        self.ensure_one()
        ten = self.env['rp.sharepoint.config']._ten_sp(ten)
        if len(noi_dung) > TRAN:
            raise UserError(_(
                'Tệp "%(t)s" nặng %(m)s MB, vượt mức %(x)s MB.',
                t=ten, m=len(noi_dung) // 1024 // 1024,
                x=TRAN // 1024 // 1024))
        d = cfg.drive_id
        if len(noi_dung) <= NGUONG_PUT:
            r = requests.put(
                '%s/drives/%s/items/%s:/%s:/content'
                % ('https://graph.microsoft.com/v1.0', d, self.sp_item_id,
                   requests.utils.quote(ten)),
                headers={'Authorization': 'Bearer ' + tok,
                         'Content-Type': 'application/octet-stream'},
                data=noi_dung, timeout=TIMEOUT)
        else:
            s = cfg._goi(tok, 'POST',
                         '/drives/%s/items/%s:/%s:/createUploadSession'
                         % (d, self.sp_item_id,
                            requests.utils.quote(ten)),
                         json={'item': {
                             '@microsoft.graph.conflictBehavior': 'replace'}})
            if s.status_code not in (200, 201):
                raise UserError(_('Mở phiên tải "%(t)s" lỗi HTTP %(m)s.',
                                  t=ten, m=s.status_code))
            r = requests.put(
                s.json()['uploadUrl'], data=noi_dung, timeout=TIMEOUT,
                headers={'Content-Length': str(len(noi_dung)),
                         'Content-Range': 'bytes 0-%d/%d'
                                          % (len(noi_dung) - 1,
                                             len(noi_dung))})
        if r.status_code not in (200, 201):
            raise UserError(_('Đưa tệp "%(t)s" lên lỗi HTTP %(m)s.',
                              t=ten, m=r.status_code))
        self._ghi_tep(r.json())

    def _ghi_tep(self, j):
        """Ghi hoặc cập nhật con trỏ tới một tệp SharePoint."""
        self.ensure_one()
        T = self.env['rp.doc.file']
        vals = {
            'folder_id': self.id, 'name': j.get('name'),
            'sp_item_id': j.get('id'), 'sp_url': j.get('webUrl'),
            'size': j.get('size') or 0,
            'date_modified': (j.get('lastModifiedDateTime') or '')
            .replace('T', ' ').replace('Z', '')[:19] or False,
            'modified_by': (j.get('lastModifiedBy') or {})
            .get('user', {}).get('displayName'),
            'mimetype': (j.get('file') or {}).get('mimeType'),
        }
        cu = T.search([('folder_id', '=', self.id),
                       ('sp_item_id', '=', j.get('id'))], limit=1)
        return cu.write(vals) if cu else T.create(vals)

    def action_lam_moi(self):
        """Đọc ngược từ SharePoint: tệp ai thả thẳng vào cũng hiện ra."""
        cfg = self._cfg()
        tok = cfg._token()
        n = 0
        for f in self.filtered('sp_item_id'):
            n += f._lam_moi_mot(cfg, tok)
        return self._bao(_('Đã đồng bộ %s tệp từ SharePoint.', n))

    def _lam_moi_mot(self, cfg, tok):
        self.ensure_one()
        con, url = [], ('/drives/%s/items/%s/children?$top=200'
                        % (cfg.drive_id, self.sp_item_id))
        while url:
            r = cfg._goi(tok, 'GET', url)
            if r.status_code != 200:
                raise UserError(_('Đọc thư mục "%(d)s" lỗi HTTP %(m)s.',
                                  d=self.display_name, m=r.status_code))
            j = r.json()
            con += [x for x in j.get('value', []) if 'file' in x]
            tiep = j.get('@odata.nextLink')
            url = tiep.split('/v1.0', 1)[1] if tiep else None
        for x in con:
            self._ghi_tep(x)
        # Tệp đã bị xoá trên SharePoint thì bỏ con trỏ, nếu không Odoo
        # báo thư mục có hồ sơ trong khi thật ra không còn gì.
        self.file_ids.filtered(
            lambda t: t.sp_item_id not in {x['id'] for x in con}).unlink()
        return len(con)

    def _bao(self, loi_nhan):
        return {'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {'type': 'success', 'message': loi_nhan,
                           'next': {'type': 'ir.actions.act_window_close'}}}

    # Đếm tệp theo SharePoint chứ không theo đính kèm Odoo.
    @api.depends('file_ids', 'is_required', 'tool_model_id',
                 'child_ids.file_count_total',
                 'child_ids.is_empty_required')
    def _compute_file_count(self):
        for f in self:
            rieng = len(f.file_ids)
            f.file_count = rieng
            f.file_count_total = rieng + sum(
                f.child_ids.mapped('file_count_total'))
            f.is_empty_required = bool(
                f.is_required and not f.tool_model_id
                and not f.file_count_total)
