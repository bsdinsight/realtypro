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
