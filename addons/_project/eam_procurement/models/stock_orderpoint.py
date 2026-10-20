# -*- coding: utf-8 -*-
"""Thiếu hàng → Yêu cầu mua của Realty, không đi thẳng ra đơn mua.

Odoo bổ sung tồn bằng cách sinh thẳng **đơn mua nháp**. Với vật tư rẻ thì
đúng và nhanh. Với một con hộp số vài tỷ thì sai quy trình: tiền
đó phải qua **Yêu cầu mua** có người duyệt trước khi thành đơn mua.

Nên ở đây tách theo NGƯỠNG GIÁ TRỊ, không tách theo loại hàng: loại hàng
đổi theo thời gian, còn thẩm quyền chi tiền thì không.

Module này là cầu — ai cài cả EAMOne lẫn bộ Mua sắm Realty thì mới có.
Khách chạy EAMOne thuần vẫn dùng bổ sung tồn gốc của Odoo như thường.
"""
from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError

PARAM_NGUONG = 'eam_procurement.nguong_yeu_cau_mua'


class StockWarehouseOrderpoint(models.Model):
    _inherit = 'stock.warehouse.orderpoint'

    eam_request_id = fields.Many2one(
        'rp.purchase.request', string='Yêu cầu mua đã lập', readonly=True,
        copy=False)

    def _eam_nguong(self):
        """Ngưỡng giá trị bắt buộc qua Yêu cầu mua. 0 = mọi thứ đều qua."""
        v = self.env['ir.config_parameter'].sudo().get_param(
            PARAM_NGUONG, '100000000')
        try:
            return float(v)
        except (TypeError, ValueError):
            return 100000000.0


    def _eam_can_dat(self):
        """Số lượng cần đặt, tính TƯỜNG MINH chứ không dùng ``qty_to_order``.

        Trên bản demo, ``qty_to_order`` của Odoo lệch hẳn với tồn thật:
        ắc-quy còn 7, định mức tối thiểu 2, mà vẫn báo cần đặt 6 — vì
        ``qty_forecast`` của nó trả về 0 trong khi ``qty_on_hand`` trả về
        7. Đã loại trừ hai khả năng: giá trị cũ chưa tính lại (tính lại
        vẫn ra 0) và định mức đặt ở vị trí cha không thấy hàng trong ô
        con (dời định mức xuống đúng ô vẫn ra 0). Chưa truy ra gốc.

        Mua hàng bằng một con số không giải thích được thì sai lúc nào
        cũng không ai biết. Nên ở đây tính thẳng theo luật nghiệp vụ:
        **dưới tối thiểu thì bù lên tối đa**.
        """
        self.ensure_one()
        con = self.product_id.with_context(
            location=self.location_id.id).qty_available
        if con >= self.product_min_qty:
            return 0.0
        dich = max(self.product_max_qty, self.product_min_qty)
        return max(0.0, dich - con)

    def action_tao_yeu_cau_mua(self):
        """Gom các dòng thiếu thành MỘT yêu cầu mua cho mỗi dự án.

        Gom chứ không tách từng dòng: người duyệt cần nhìn tổng số tiền
        của một đợt bổ sung, chứ duyệt lẻ hai chục phiếu thì không ai
        thấy được bức tranh.
        """
        PR = self.env['rp.purchase.request']
        can = self.filtered(lambda o: not o.eam_request_id)
        if not can:
            raise UserError(_(
                'Các dòng đã chọn đều đã lập yêu cầu mua rồi.'))
        nguong = self._eam_nguong()
        dong = []
        tong = 0.0
        for o in can:
            sl = o._eam_can_dat()
            if sl <= 0:
                continue
            gia = o.product_id.standard_price or 0.0
            tong += sl * gia
            dong.append((0, 0, {
                'name': o.product_id.display_name,
                'product_id': o.product_id.id,
                'quantity': sl,
                'price_estimated': gia,
            }))
        if not dong:
            raise UserError(_(
                'Không dòng nào có số lượng cần đặt lớn hơn 0.'))
        if tong < nguong:
            # Định dạng số NGOÀI _(): chuỗi dịch chỉ nhận %(ten)s, nhét
            # thêm quy cách số vào là nổ lúc chạy chứ không phải lúc nạp.
            raise UserError(_(
                'Tổng giá trị %(t)s thấp hơn ngưỡng %(n)s nên không cần '
                'qua Yêu cầu mua — bấm "Đặt hàng" của Odoo để ra đơn mua '
                'thẳng.\n\nNgưỡng đổi ở Tham số hệ thống "%(p)s".',
                t='{:,.0f}'.format(tong), n='{:,.0f}'.format(nguong),
                p=PARAM_NGUONG))
        r = PR.create({
            'reason': _('Bổ sung tồn kho phụ tùng — %(n)d mặt hàng dưới '
                        'định mức tối thiểu', n=len(dong)),
            'requester_id': self.env.user.id,
            'date_request': fields.Date.context_today(self),
            'line_ids': dong,
        })
        can.write({'eam_request_id': r.id})
        # Dịch TRƯỚC rồi mới thay giá trị vào, và bọc Markup — nếu không
        # thì thẻ <b> hiện ra thành chữ, còn giá trị người dùng nhập lại
        # không được thoát.
        r.message_post(body=Markup(
            _('Lập từ <b>bổ sung tồn kho</b>: %(n)s mặt hàng dưới định '
              'mức, ước %(t)s.',
              n=len(dong), t='{:,.0f}'.format(tong))))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'rp.purchase.request',
            'res_id': r.id, 'view_mode': 'form',
        }
