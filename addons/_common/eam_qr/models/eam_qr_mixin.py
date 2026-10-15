# -*- coding: utf-8 -*-
"""Mã quét cho vị trí và thiết bị.

Dán mã lên CHỖ, không dán lên THIẾT BỊ — và vì sao nó quan trọng
----------------------------------------------------------------
Tem dán trên vỏ tháp là tem của **vị trí** (trụ T07), không phải của
thiết bị. Hộp số bên trong sẽ bị tháo ra đem về xưởng và thay bằng cái
khác; tua-bin vẫn là T07.

Hệ nào mã hoá *mã thiết bị* vào tem dán trên tháp thì sau hai năm luân
chuyển phụ tùng, **mọi tem ngoài hiện trường trỏ sai** — và sai một cách
im lặng: người thợ quét tem trên trụ T07, màn hình mở ra một hộp số
đang nằm trong kho, và họ ghi số đo của máy này vào hồ sơ của máy khác.

Nên tem vị trí **không trỏ tới thiết bị nào cả**: nó trỏ tới chỗ, rồi
hệ thống tra lịch sử lắp đặt để biết **hôm nay** chỗ đó đang là cái gì.
Thiết bị vẫn có tem riêng — dán lên chính nó, theo nó đi khắp nơi —
nhưng đó là tem khác, mang tiền tố khác.

Vì sao mã có TIỀN TỐ và là chuỗi ngẫu nhiên
--------------------------------------------
``L`` cho vị trí, ``A`` cho thiết bị. Tiền tố làm hai việc: người đọc
tem biết ngay mình đang cầm loại tem nào, và mã gõ sai **không bao giờ
mở ra đúng một bản ghi khác loại**.

Ngẫu nhiên thay vì số thứ tự vì số thứ tự thì ai cũng dò được
``/eam/q/1`` tới ``/eam/q/9999`` để đếm xem nhà máy có bao nhiêu thiết
bị — và biết số lượng tài sản của một nhà máy là một thông tin.

NFC không cần thêm mã nguồn nào
--------------------------------
Thẻ NFC chỉ lưu một URL. Cùng đường dẫn ``/eam/q/<mã>`` này ghi vào thẻ
NFC là chạy y hệt — việc ghi thẻ làm bằng ứng dụng điện thoại, không
phải việc của phần mềm quản lý. Nên phần "NFC" của yêu cầu được đáp ứng
bằng chính cái đã có, và nói thẳng như vậy thì tốt hơn là dựng thêm một
module NFC cho đẹp danh mục.
"""
import secrets
from urllib.parse import quote

from odoo import _, api, fields, models

DAI_MA = 10


class EamQrMixin(models.AbstractModel):
    _name = 'eam.qr.mixin'
    _description = 'Mã quét hiện trường'

    _qr_prefix = 'X'

    qr_token = fields.Char(
        string='Mã quét', index=True, copy=False, readonly=True,
        help='Mã in trên tem QR dán ngoài hiện trường. Ngẫu nhiên, có '
             'tiền tố theo loại — không phải số thứ tự, để không ai dò '
             'được số lượng thiết bị của nhà máy.')
    qr_url = fields.Char(string='Đường dẫn quét', compute='_compute_qr')
    qr_image_url = fields.Char(string='Ảnh QR', compute='_compute_qr')

    @api.depends('qr_token')
    def _compute_qr(self):
        goc = self.env['ir.config_parameter'].sudo().get_param(
            'web.base.url', '')
        for r in self:
            if not r.qr_token:
                r.qr_url = r.qr_image_url = False
                continue
            r.qr_url = '%s/eam/q/%s' % (goc.rstrip('/'), r.qr_token)
            # Phải mã hoá giá trị: nó là một URL đầy đủ nằm trong tham số
            # truy vấn của một URL khác. Không mã hoá thì chỉ cần
            # `web.base.url` có dấu `&` hay `?` là ảnh QR sinh ra một mã
            # bị cắt — mà lỗi đó chỉ lộ ra sau khi tem đã in và dán.
            r.qr_image_url = (
                '/report/barcode/?barcode_type=QR&value=%s'
                '&width=300&height=300' % quote(r.qr_url, safe=''))

    def _sinh_token(self):
        """Cấp mã cho những bản ghi chưa có. Không cấp lại mã đã có.

        Cấp lại là làm chết mọi tem đã dán ngoài hiện trường — nên hàm
        này cố ý bỏ qua bản ghi đã có mã, và việc đổi mã phải gọi riêng.
        """
        for r in self:
            if r.qr_token:
                continue
            for _lan in range(10):
                ma = r._qr_prefix + secrets.token_urlsafe(DAI_MA)[:DAI_MA]
                if not r.sudo().search_count([('qr_token', '=', ma)]):
                    r.qr_token = ma
                    break
        return True

    def action_sinh_qr(self):
        self._sinh_token()
        return True

    def action_doi_qr(self):
        """Đổi mã — dùng khi tem bị sao chép hoặc dán sai chỗ.

        Tách riêng khỏi hàm cấp mã vì nó **làm chết tem cũ**: mọi tem
        đang dán ngoài hiện trường của bản ghi này sẽ không mở được gì
        nữa, phải in và dán lại.
        """
        for r in self:
            r.qr_token = False
        self._sinh_token()
        for r in self:
            if hasattr(r, 'message_post'):
                r.message_post(body=_(
                    'Đã đổi mã quét. Tem cũ dán ngoài hiện trường không '
                    'còn mở được gì — phải in và dán lại.'))
        return True

    @api.model
    def giai_ma_tem(self, token):
        """Giải một mã tem thành bản ghi, cho app hiện trường gọi.

        App KHÔNG nên đi qua đường dẫn ``/eam/q/<mã>`` của trình duyệt:
        đường đó trả về chuyển hướng HTML, mà app thì cần dữ liệu. Nên
        có một cửa riêng trả JSON.

        Tem VỊ TRÍ được giải qua lịch sử lắp đặt — trả về thiết bị đang
        lắp ở đó HÔM NAY, kèm cả vị trí để người quét biết mình đang
        đứng ở đâu. Đây là chỗ cả tính năng có nghĩa: dán mã theo thiết
        bị thì sau vài lần luân chuyển phụ tùng mọi tem đều trỏ sai.
        """
        token = (token or '').strip()
        if not token:
            return {'ok': False, 'ly_do': _('Tem không mang mã nào.')}
        loai = token[:1]
        if loai not in ('L', 'A'):
            return {'ok': False, 'ly_do': _(
                'Mã phải bắt đầu bằng "L" (tem vị trí) hoặc "A" (tem '
                'thiết bị). Nhận được: %s', token)}

        vt = ts = None
        if loai == 'L':
            vt = self.env['eam.location'].search(
                [('qr_token', '=', token)], limit=1)
            if not vt:
                return {'ok': False, 'ly_do': _(
                    'Không có vị trí nào mang mã "%s". Tem có thể đã được '
                    'cấp lại mã — đừng ghi số đo vào hồ sơ khác, báo người '
                    'quản lý tài sản.', token)}
            hn = fields.Date.context_today(vt)
            lap = self.env['eam.installation'].search(
                [('location_id', '=', vt.id),
                 ('date_install', '<=', hn),
                 '|', ('date_remove', '=', False),
                 ('date_remove', '>=', hn)],
                order='date_install desc', limit=1)
            ts = lap.asset_id or None
        else:
            ts = self.env['eam.asset'].search(
                [('qr_token', '=', token)], limit=1)
            if not ts:
                return {'ok': False, 'ly_do': _(
                    'Không có thiết bị nào mang mã "%s".', token)}
            vt = ts.current_location_id or None

        W = self.env['eam.work.order']
        dom = [('state', 'in', ('approved', 'planned', 'in_progress'))]
        dom += ([('location_id', '=', vt.id)] if vt
                else [('asset_id', '=', ts.id)])
        lenh = W.search(dom, order='date_planned_start', limit=20)

        return {
            'ok': True,
            'loai_tem': 'vị trí' if loai == 'L' else 'thiết bị',
            'location_id': vt.id if vt else False,
            'location': vt.complete_name if vt else '',
            'location_code': vt.complete_code if vt else '',
            'asset_id': ts.id if ts else False,
            'asset': ts.display_name if ts else '',
            'asset_code': ts.code if ts else '',
            'serial_no': (ts.serial_no or '') if ts else '',
            'warranty_state': (ts.warranty_state or '') if ts else '',
            # Vị trí trống KHÔNG phải lỗi — nó là một sự thật cần nói ra.
            'trong': bool(vt and not ts),
            'wo': [{'id': w.id, 'name': w.name, 'title': w.title,
                    'state': w.state} for w in lenh],
        }

    @api.model
    def _cap_ma_thieu(self):
        """Cấp mã cho mọi bản ghi còn thiếu. Gọi từ nút hoặc cron."""
        ds = self.search([('qr_token', '=', False)])
        ds._sinh_token()
        return len(ds)


class EamLocation(models.Model):
    _name = 'eam.location'
    _inherit = ['eam.location', 'eam.qr.mixin']

    _qr_prefix = 'L'

    _uniq_qr = models.Constraint(
        'UNIQUE(qr_token)', 'Mã quét vị trí không được trùng.')

    def action_in_tem_qr(self):
        return self.env.ref('eam_qr.action_report_location_label') \
            .report_action(self)


class EamAsset(models.Model):
    _name = 'eam.asset'
    _inherit = ['eam.asset', 'eam.qr.mixin']

    _qr_prefix = 'A'

    _uniq_qr = models.Constraint(
        'UNIQUE(qr_token)', 'Mã quét thiết bị không được trùng.')

    def action_in_tem_qr(self):
        return self.env.ref('eam_qr.action_report_asset_label') \
            .report_action(self)
