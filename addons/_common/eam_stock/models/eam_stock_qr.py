# -*- coding: utf-8 -*-
"""Quét QR cho thao tác kho (KHO-39).

Dựng trên ``eam.qr.mixin`` đã có của EAMOne chứ không mua `stock_barcode`
của bản Enterprise: hạ tầng tem, sinh mã, in tem và cửa giải mã cho app
hiện trường đều sẵn rồi. Việc còn lại là cấp tem cho hai thứ mà kho cần
quét — **ô chứa** và **lô/sê-ri** — rồi dạy cửa giải mã nhận ra chúng.

Tiền tố mã nói lên loại
------------------------
``L`` vị trí chức năng · ``A`` thiết bị · ``K`` ô chứa trong kho ·
``S`` lô/sê-ri. Nhìn mã là biết quét trúng cái gì, kể cả khi tem bong
chữ. Mã ngẫu nhiên chứ không phải số thứ tự — số thứ tự thì ai cầm một
tem cũng đoán được kho có bao nhiêu thứ.

Quét ra cái gì thì làm gì
--------------------------
Cửa giải mã trả luôn **việc làm được tiếp**, vì người đứng giữa kho cầm
điện thoại cần biết bấm gì chứ không cần một bảng dữ liệu. Quét ô chứa
thì ra danh sách hàng trong ô; quét lô thì ra con hàng đó đang ở đâu,
còn hạn không, có đang bị khoá không.
"""
from odoo import _, api, fields, models


class StockLocationQr(models.Model):
    _name = 'stock.location'
    _inherit = ['stock.location', 'eam.qr.mixin']

    _qr_prefix = 'K'

    _uniq_qr = models.Constraint(
        'UNIQUE(qr_token)', 'Mã quét ô chứa không được trùng.')


class StockLotQr(models.Model):
    _name = 'stock.lot'
    _inherit = ['stock.lot', 'eam.qr.mixin']

    _qr_prefix = 'S'

    _uniq_qr = models.Constraint(
        'UNIQUE(qr_token)', 'Mã quét lô/sê-ri không được trùng.')


class EamQrMixinStock(models.AbstractModel):
    _inherit = 'eam.qr.mixin'

    @api.model
    def giai_ma_tem(self, token):
        """Nhận thêm tem kho (K) và tem lô (S); còn lại trả về bản gốc."""
        token = (token or '').strip()
        loai = token[:1]
        if loai not in ('K', 'S'):
            kq = super().giai_ma_tem(token)
            # Bản gốc chỉ biết hai loại tem nên câu báo lỗi của nó liệt
            # kê thiếu. Người cầm tem kho mà đọc "chỉ nhận L hoặc A" sẽ
            # tưởng tem của mình hỏng.
            if not kq.get('ok') and loai not in ('L', 'A'):
                kq['ly_do'] = _(
                    'Mã phải bắt đầu bằng "L" (vị trí chức năng), "A" '
                    '(thiết bị), "K" (ô chứa trong kho) hoặc "S" (lô / '
                    'sê-ri). Nhận được: %s', token or '(rỗng)')
            return kq

        if loai == 'K':
            vt = self.env['stock.location'].search(
                [('qr_token', '=', token)], limit=1)
            if not vt:
                return {'ok': False, 'ly_do': _(
                    'Không có ô chứa nào mang mã "%s".', token)}
            quants = self.env['stock.quant'].search(
                [('location_id', '=', vt.id), ('quantity', '!=', 0)])
            return {
                'ok': True, 'loai': 'o_chua',
                'vi_tri': {'id': vt.id, 'ten': vt.complete_name,
                           'kho': vt.warehouse_id.name or '',
                           'dung_duoc': not vt.eam_cam_xuat},
                'hang': [{
                    'san_pham': q.product_id.display_name,
                    'ma': q.product_id.default_code or '',
                    'so_luong': q.quantity,
                    'don_vi': q.product_id.uom_id.name,
                    'lo': q.lot_id.name or '',
                    'chu_so_huu': q.owner_id.name or '',
                } for q in quants],
                'viec_lam_duoc': (
                    ['kiem_ke', 'chuyen_kho'] if not vt.eam_cam_xuat
                    else ['kiem_ke']),
            }

        lo = self.env['stock.lot'].search(
            [('qr_token', '=', token)], limit=1)
        if not lo:
            return {'ok': False, 'ly_do': _(
                'Không có lô/sê-ri nào mang mã "%s".', token)}
        hn = fields.Date.context_today(self)
        q = self.env['stock.quant'].search(
            [('lot_id', '=', lo.id), ('location_id.usage', '=', 'internal'),
             ('quantity', '>', 0)], limit=1)
        canh = []
        if lo.expiration_date and lo.expiration_date.date() < hn:
            canh.append(_('ĐÃ HẾT HẠN từ %s', lo.expiration_date.date()))
        if lo.eam_calib_due and not lo.eam_dung_duoc:
            canh.append(_('KHÔNG dùng được — hiệu chuẩn hết hiệu lực'))
        if q and q.location_id.eam_cam_xuat:
            canh.append(_('Đang ở "%s" — chưa dùng được',
                          q.location_id.name))
        return {
            'ok': True, 'loai': 'lo',
            'lo': {'id': lo.id, 'ten': lo.name,
                   'san_pham': lo.product_id.display_name,
                   'ma': lo.product_id.default_code or '',
                   'ngay_san_xuat': str(lo.eam_mfg_date or ''),
                   'han_dung': str(lo.expiration_date or ''),
                   'bao_hanh_den': str(lo.eam_warranty_end or ''),
                   'tai_san': lo.eam_asset_id.display_name or ''},
            'dang_o': q.location_id.complete_name if q else '',
            'so_luong': q.quantity if q else 0.0,
            'canh_bao': canh,
            'viec_lam_duoc': ['xem_tai_san'] if lo.eam_asset_id else [],
        }
