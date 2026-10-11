# -*- coding: utf-8 -*-
"""Xem tệp hồ sơ ngay trong Odoo, dù tệp nằm trên SharePoint.

Luật "một bản" giải quyết được chuyện hai bản lệch nhau, nhưng đẻ ra một
chuyện khác: người mở biên bản trong Odoo mà không có tài khoản SharePoint
thì chỉ thấy tên tệp. Với một dự án EPC có hàng chục kỹ sư hiện trường và
tư vấn giám sát, bắt ai cũng phải có chỗ trên site SharePoint là không
thực tế.

May là Odoo gọi Graph bằng **danh nghĩa ứng dụng** (client credentials),
không thay mặt ai đăng nhập — nên nó luôn đọc được tệp. Chỗ này chỉ chuyển
tiếp dòng byte đó về trình duyệt sau khi đã kiểm quyền Odoo. Không sinh
thêm bản nào: không ghi xuống đĩa, không tạo ir.attachment.

Hệ quả phải nói rõ: **ai đọc được bản ghi trong Odoo là đọc được hồ sơ của
nó**, bất kể quyền trên SharePoint. Đó là ranh giới quyền cố ý chọn — sổ
giữ ý nghĩa thì sổ cũng giữ luôn quyền.
"""
import requests

from odoo import _, http
from odoo.exceptions import UserError
from odoo.http import content_disposition, request

# Trên mức này thì không gánh qua Odoo nữa mà đẩy thẳng trình duyệt sang
# đường tải dùng-một-lần của Graph: giữ cả tệp trong bộ nhớ tiến trình
# Odoo để phục vụ một lượt xem là cách nhanh nhất làm ngã máy chủ.
TRAN_GANH = 50 * 1024 * 1024
TIMEOUT = 180


class RpDocFileController(http.Controller):

    @http.route('/rp_doc/file/<int:file_id>', type='http', auth='user')
    def xem_tep(self, file_id, dl=None, **kw):
        rec = request.env['rp.doc.file'].browse(file_id)
        if not rec.exists():
            raise UserError(_('Tệp không còn trong hệ thống.'))
        # Kiểm quyền TRƯỚC khi sudo — sudo rồi mới kiểm là không kiểm gì.
        rec.check_access('read')
        rec = rec.sudo()
        if not rec.sp_item_id:
            raise UserError(_('Tệp này chưa có trên SharePoint.'))

        cfg = request.env['rp.sharepoint.config'].sudo()._lay()
        tok = cfg._token()
        r = cfg._goi(tok, 'GET',
                     '/drives/%s/items/%s' % (cfg.drive_id, rec.sp_item_id))
        if r.status_code == 404:
            raise UserError(_(
                'Tệp "%s" không còn trên SharePoint — có thể ai đó đã xoá '
                'hoặc chuyển đi. Bấm "Làm mới từ SharePoint" ở thư mục để '
                'Odoo cập nhật lại.', rec.name))
        if r.status_code != 200:
            raise UserError(_('Đọc tệp từ SharePoint lỗi HTTP %s.',
                              r.status_code))
        j = r.json()
        url = j.get('@microsoft.graph.downloadUrl')
        if not url:
            raise UserError(_('SharePoint không trả đường tải cho tệp này.'))

        if (j.get('size') or 0) > TRAN_GANH:
            return request.redirect(url, local=False)

        d = requests.get(url, timeout=TIMEOUT)
        if d.status_code != 200:
            raise UserError(_('Tải tệp về lỗi HTTP %s.', d.status_code))

        ten = rec.name or j.get('name') or 'tep'
        kieu = rec.mimetype or j.get('file', {}).get('mimeType') \
            or 'application/octet-stream'
        if dl:
            bo_tri = content_disposition(ten)
        else:
            # Xem tại chỗ: PDF và ảnh mở thẳng trong trình duyệt, khỏi
            # phải tải về rồi mở bằng tay chỉ để liếc một trang.
            bo_tri = "inline; filename*=UTF-8''%s" % requests.utils.quote(ten)
        return request.make_response(d.content, headers=[
            ('Content-Type', kieu),
            ('Content-Length', str(len(d.content))),
            ('Content-Disposition', bo_tri),
        ])
