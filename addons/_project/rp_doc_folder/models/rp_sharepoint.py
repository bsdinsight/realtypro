# -*- coding: utf-8 -*-
import logging
from urllib.parse import quote, urlparse

import requests

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

GRAPH = 'https://graph.microsoft.com/v1.0'
TIMEOUT = 30


class RpSharepointConfig(models.Model):
    """Thông số đấu nối SharePoint Online — một bản ghi cho cả hệ thống.

    Odoo gọi Graph bằng danh nghĩa ỨNG DỤNG (client credentials), không
    thay mặt ai đăng nhập. Vì vậy quyền phải là loại *Application* và
    phải được admin tenant đồng ý; `Sites.Selected` thì còn phải chỉ
    đích danh từng site nữa. Ba chỗ này sai thì lỗi chỉ lộ ra lúc chạy
    thật và thông báo của Microsoft gần như không nói được nguyên nhân —
    nên nút "Kiểm tra kết nối" ở đây tự tách ra bốn tầng và nói đúng
    tầng nào hỏng.

    Client secret cất trong bảng này, tức nằm trong cơ sở dữ liệu. Nó
    không hiện lại trên giao diện sau khi lưu, nhưng ai đọc được DB thì
    đọc được nó — đây là lý do phải hẹn ngày hết hạn và xoay khoá, chứ
    không phải chuyện cất một lần rồi quên.
    """
    _name = 'rp.sharepoint.config'
    _description = 'Cấu hình SharePoint'

    name = fields.Char(default='SharePoint Online', readonly=True)
    # Không đặt required ở tầng model: bản ghi cấu hình phải tạo
    # được khi còn rỗng thì mới mở được form ra mà điền. Bắt buộc
    # kiểm ở nút Kiểm tra kết nối, nơi nói được rõ thiếu cái gì.
    tenant_id = fields.Char(string='Tenant ID')
    client_id = fields.Char(string='Client ID (Application ID)')
    client_secret = fields.Char(
        string='Client secret',
        help='Chuỗi ở cột Value khi tạo secret, KHÔNG phải Secret ID.')
    site_url = fields.Char(
        string='URL site',
        help='Tới hết tên site, ví dụ '
             'https://congty.sharepoint.com/sites/Demo')
    secret_expire = fields.Date(
        string='Secret hết hạn ngày',
        help='Hết hạn thì đồng bộ ngừng và lỗi Microsoft trả về rất khó '
             'đoán nguyên nhân. Khai ở đây để hệ thống cảnh báo trước.')

    site_id = fields.Char(string='Graph Site ID', readonly=True, copy=False)
    drive_id = fields.Char(string='Thư viện tài liệu', readonly=True,
                           copy=False)
    state = fields.Selection(
        [('draft', 'Chưa kiểm tra'), ('ok', 'Đã thông'),
         ('error', 'Lỗi')], default='draft', readonly=True)
    last_check = fields.Datetime(string='Kiểm tra lần cuối', readonly=True)
    last_message = fields.Text(string='Kết quả kiểm tra', readonly=True)

    @api.model
    def _lay(self):
        cfg = self.search([], limit=1)
        return cfg or self.create({})

    # ------------------------------------------------------------------
    def _token(self):
        """Lấy access token theo luồng client credentials."""
        self.ensure_one()
        r = requests.post(
            'https://login.microsoftonline.com/%s/oauth2/v2.0/token'
            % self.tenant_id,
            data={'grant_type': 'client_credentials',
                  'client_id': self.client_id,
                  'client_secret': self.client_secret,
                  'scope': 'https://graph.microsoft.com/.default'},
            timeout=TIMEOUT)
        if r.status_code != 200:
            # KHÔNG đưa nội dung trả về vào thông báo: nó có thể vọng lại
            # một phần thông số gửi đi.
            raise UserError(_(
                'Không lấy được token (HTTP %s). Thường là một trong ba: '
                'Tenant ID sai, Client ID sai, hoặc client secret sai '
                'hay đã hết hạn.', r.status_code))
        return r.json()['access_token']

    def _goi(self, tok, method, path, **kw):
        r = requests.request(method, GRAPH + path, timeout=TIMEOUT,
                             headers={'Authorization': 'Bearer ' + tok},
                             **kw)
        return r

    def _duong_dan_site(self):
        """Tách URL site thành phần Graph hiểu được."""
        self.ensure_one()
        u = urlparse((self.site_url or '').strip().rstrip('/'))
        if not u.hostname or not u.path:
            raise UserError(_(
                'URL site không đúng dạng. Phải là '
                'https://congty.sharepoint.com/sites/TenSite'))
        return u.hostname, u.path

    # ------------------------------------------------------------------
    def action_kiem_tra(self):
        """Bốn tầng, dừng ở tầng đầu tiên hỏng và nói rõ phải sửa gì."""
        self.ensure_one()
        thieu = [n for f, n in (('tenant_id', 'Tenant ID'),
                                ('client_id', 'Client ID'),
                                ('client_secret', 'Client secret'),
                                ('site_url', 'URL site')) if not self[f]]
        if thieu:
            raise UserError(_('Còn thiếu: %s.', ', '.join(thieu)))
        buoc = []
        try:
            tok = self._token()
            buoc.append('✓ Lấy được token — Tenant ID, Client ID và '
                        'secret đều đúng.')

            host, duong = self._duong_dan_site()
            r = self._goi(tok, 'GET', '/sites/%s:%s' % (host, duong))
            if r.status_code == 403:
                raise UserError('\n'.join(buoc + [
                    '✗ Có token nhưng KHÔNG đọc được site.',
                    '',
                    'Đây gần như chắc chắn là thiếu bước chỉ đích danh '
                    'site: Sites.Selected mặc định không cho ứng dụng '
                    'chạm vào site nào cả, kể cả khi đã Grant admin '
                    'consent. Phải gọi thêm một lệnh Graph cấp role '
                    '"write" cho Client ID trên đúng site này — xem mục '
                    '4b trong tài liệu SHAREPOINT_SETUP.md.']))
            if r.status_code == 404:
                raise UserError('\n'.join(buoc + [
                    '✗ Không tìm thấy site "%s%s".' % (host, duong),
                    'Kiểm lại URL site — phải tới hết tên site và không '
                    'kèm đuôi nào phía sau.']))
            if r.status_code != 200:
                raise UserError('\n'.join(buoc + [
                    '✗ Đọc site trả về HTTP %s.' % r.status_code]))
            sid = r.json()['id']
            buoc.append('✓ Đọc được site: %s' % r.json().get('displayName'))

            r = self._goi(tok, 'GET', '/sites/%s/drive' % sid)
            if r.status_code != 200:
                raise UserError('\n'.join(buoc + [
                    '✗ Không đọc được thư viện tài liệu (HTTP %s).'
                    % r.status_code]))
            did = r.json()['id']
            buoc.append('✓ Thấy thư viện: %s' % r.json().get('name'))

            # Tầng cuối: thử GHI. Đọc được không có nghĩa là ghi được —
            # cấp nhầm role "read" ở bước 4b thì ba tầng trên đều xanh
            # mà đến lúc dựng thư mục mới hỏng.
            thu = '_rp_kiem_tra_ghi'
            r = self._goi(
                tok, 'POST', '/drives/%s/root/children' % did,
                json={'name': thu, 'folder': {},
                      '@microsoft.graph.conflictBehavior': 'replace'})
            if r.status_code == 403:
                raise UserError('\n'.join(buoc + [
                    '✗ Đọc được nhưng KHÔNG ghi được.',
                    '',
                    'Ở bước 4b đã cấp role "read" thay vì "write". Gọi '
                    'lại lệnh cấp quyền với "roles": ["write"].']))
            if r.status_code not in (200, 201):
                raise UserError('\n'.join(buoc + [
                    '✗ Thử tạo thư mục trả về HTTP %s.' % r.status_code]))
            self._goi(tok, 'DELETE',
                      '/drives/%s/items/%s' % (did, r.json()['id']))
            buoc.append('✓ Ghi được — đã tạo rồi xoá một thư mục thử.')

            self.write({'site_id': sid, 'drive_id': did, 'state': 'ok',
                        'last_check': fields.Datetime.now(),
                        'last_message': '\n'.join(buoc)})
        except UserError as e:
            self.write({'state': 'error',
                        'last_check': fields.Datetime.now(),
                        'last_message': str(e)})
            # Ghi lại rồi mới ném, để kết quả còn trên màn hình.
            self.env.cr.commit()
            raise
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'type': 'success', 'title': _('Kết nối đã thông'),
                       'message': '\n'.join(buoc), 'sticky': True},
        }

    # ------------------------------------------------------------------
    def rp_dung_cay(self, project):
        """Dựng cây thư mục của dự án lên SharePoint.

        Chạy lại được: thư mục đã có neo ``sp_item_id`` thì bỏ qua, nên
        bổ sung thư mục mới vào bộ chuẩn rồi chạy lại là chỉ tạo phần
        thiếu. Dùng conflictBehavior=replace để thư mục ai đó đã tạo tay
        trùng tên thì nhận luôn chứ không nhân đôi.
        """
        self.ensure_one()
        if not (self.site_id and self.drive_id):
            raise UserError(_('Bấm "Kiểm tra kết nối" trước đã.'))
        tok = self._token()
        goc = '%s/%s' % (project.code or 'DA', project.name or '')
        tao = 0
        for f in project.doc_folder_ids.sorted(
                lambda x: (len((x.code or '').split('.')), x.code or '')):
            if f.sp_item_id:
                continue
            duong = '%s/%s' % (goc, f.full_path)
            cha = duong.rsplit('/', 1)[0]
            ten = duong.rsplit('/', 1)[1]
            r = self._goi(
                tok, 'POST',
                '/drives/%s/root:/%s:/children' % (self.drive_id,
                                                   quote(cha)),
                json={'name': ten, 'folder': {},
                      '@microsoft.graph.conflictBehavior': 'replace'})
            if r.status_code not in (200, 201):
                raise UserError(_(
                    'Tạo thư mục "%(d)s" lỗi HTTP %(m)s. Đã tạo được '
                    '%(n)s thư mục trước đó, chạy lại sẽ tiếp từ chỗ '
                    'dừng.', d=duong, m=r.status_code, n=tao))
            j = r.json()
            f.write({'sp_drive_id': self.drive_id, 'sp_item_id': j['id'],
                     'sp_url': j.get('webUrl'),
                     'sp_synced_on': fields.Datetime.now()})
            tao += 1
        return tao
