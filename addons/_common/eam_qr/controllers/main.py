# -*- coding: utf-8 -*-
"""Giải mã tem quét: từ mã trên tem về đúng bản ghi.

Tem vị trí được giải **qua lịch sử lắp đặt**, không trỏ cứng vào thiết
bị nào. Người thợ quét tem trên trụ T07 và mở ra thứ **hôm nay** đang
nằm ở T07 — không phải thứ đã nằm ở đó lúc in tem.

``auth='user'`` làm luôn phần đăng nhập: chưa đăng nhập thì Odoo tự đưa
về trang đăng nhập rồi quay lại đúng đường dẫn này. Đó là hành vi cần
cho người đứng ngoài trụ với điện thoại — không phải lỗi cần xử lý.
"""
from odoo import _, fields, http
from odoo.http import request


class EamQrController(http.Controller):

    @http.route('/eam/q/<string:token>', type='http', auth='user',
                methods=['GET'], readonly=True)
    def quet(self, token, v=None, **kw):
        token = (token or '').strip()
        if not token:
            return self._thong_bao(
                _('Tem trống'),
                _('Đường dẫn không mang mã nào.'))

        loai = token[:1]
        if loai == 'L':
            return self._giai_vi_tri(token, buoc_vi_tri=(v == 'loc'))
        if loai == 'A':
            return self._giai_thiet_bi(token)
        return self._thong_bao(
            _('Mã không đúng dạng'),
            _('Mã quét phải bắt đầu bằng "L" (tem vị trí) hoặc "A" (tem '
              'thiết bị). Mã nhận được: %s', token))

    # ------------------------------------------------------------------
    def _giai_vi_tri(self, token, buoc_vi_tri=False):
        vt = request.env['eam.location'].search(
            [('qr_token', '=', token)], limit=1)
        if not vt:
            return self._tem_la(token, _('vị trí'))
        if buoc_vi_tri:
            return self._mo('eam_core.action_eam_location', vt.id)

        # Thiết bị đang lắp ở đây HÔM NAY — tra lịch sử lắp đặt, không
        # dùng mã cứng trên tem.
        hn = fields.Date.context_today(vt)
        lap = request.env['eam.installation'].search(
            [('location_id', '=', vt.id),
             ('date_install', '<=', hn),
             '|', ('date_remove', '=', False),
             ('date_remove', '>=', hn)],
            order='date_install desc', limit=1)
        if lap.asset_id:
            return self._mo('eam_core.action_eam_asset', lap.asset_id.id)
        return self._thong_bao(
            _('Vị trí đang trống'),
            _('Tem này là tem của vị trí %(ma)s — %(ten)s. Hôm nay không '
              'có thiết bị nào đang lắp ở đó, nên không mở được hồ sơ '
              'thiết bị.', ma=vt.complete_code or '', ten=vt.name or ''),
            lien_ket=[(_('Mở hồ sơ vị trí'),
                       self._duong_dan('eam_core.action_eam_location',
                                       vt.id))])

    def _giai_thiet_bi(self, token):
        ts = request.env['eam.asset'].search(
            [('qr_token', '=', token)], limit=1)
        if not ts:
            return self._tem_la(token, _('thiết bị'))
        return self._mo('eam_core.action_eam_asset', ts.id)

    # ------------------------------------------------------------------
    def _duong_dan(self, action_xmlid, res_id):
        return '/odoo/action-%s/%s' % (action_xmlid, res_id)

    def _mo(self, action_xmlid, res_id):
        return request.redirect(self._duong_dan(action_xmlid, res_id),
                                local=True)

    def _tem_la(self, token, loai):
        return self._thong_bao(
            _('Không tìm thấy tem'),
            _('Không có %(loai)s nào mang mã "%(ma)s". Tem có thể đã được '
              'cấp lại mã, hoặc bản ghi đã bị xoá. Đừng ghi số đo vào một '
              'hồ sơ khác — báo người quản lý tài sản để in tem mới.',
              loai=loai, ma=token))

    def _thong_bao(self, tieu_de, noi_dung, lien_ket=None):
        return request.render('eam_qr.page_thong_bao', {
            'tieu_de': tieu_de,
            'noi_dung': noi_dung,
            'lien_ket': lien_ket or [],
        })
