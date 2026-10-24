# -*- coding: utf-8 -*-
"""Đưa SẢN LƯỢNG lên bản đồ — và xoá engine khả dụng thứ ba.

Bản đồ vốn chỉ nói về dừng máy
-------------------------------
Panel bên trái đếm khoảng dừng, lệnh công việc, giờ dừng. Không một con
số sản lượng nào. Nhưng câu người vận hành hỏi mỗi sáng không phải *"có
bao nhiêu lệnh đang mở"* — mà là ***máy nào đang kéo cả trại xuống***.
Bản đồ là chỗ duy nhất trả lời được phần sau của câu ấy: **máy kém có
TỤM LẠI không**. Tụm theo hàng là hiệu ứng che gió; tụm theo nhánh là
lỗi đường dây. Bảng không nhìn ra hình.

ĐỌC, không tự tính
-------------------
Trước đây bản đồ tự cộng giờ dừng để ra khả dụng — thành ra engine khả
dụng **thứ ba**, sau sổ khả dụng và bảng tổ máy. Ba con số cho một chữ,
và chúng lệch nhau vì phạm vi khác nhau mà nhãn không nói.

Nay bản đồ đọc thẳng **bảng tổ máy** cho từng vị trí và **bảng kỳ** cho
cấp nhà máy. Khớp tờ báo cáo *theo cấu tạo*, không nhờ may.

Thiếu ngày thì NÓI, đừng tô xanh
---------------------------------
Mốc xem rơi vào ngày chưa có dữ liệu thì các ô sản lượng trả ``None``,
và chỗ tô màu hiện màu XÁM chứ không hiện màu tốt. Một bản đồ xanh rờn
trong ngày chưa có số nào là bản đồ đang nói dối.
"""
from odoo import api, fields, models


class EamLocation(models.Model):
    _inherit = 'eam.location'

    # ==================================================================
    def _map_payload_one(self, tu, den):
        """Bổ sung số sản lượng của VỊ TRÍ, đọc từ bảng tổ máy."""
        g = super()._map_payload_one(tu, den)
        U = self.env['eam.unit.day']
        ngay = den.date()
        d = U.search([('location_id', '=', self.id),
                      ('date', '=', ngay)], limit=1)
        if not d:
            g.update({
                'kwh': None, 'cf': None, 'kd_sl': None, 'kd_om': None,
                'kd_hang': None, 'lk_thang': None, 'mat_ngay': None,
                'co_so_ngay': False,
            })
            return g
        g.update({
            'kwh': round(d.san_luong, 1) if d.do_duoc_sl else None,
            'cf': round(d.he_so_cong_suat, 2) if d.do_duoc_hs else None,
            'kd_sl': round(d.kd_san_luong, 2) if d.do_duoc_kd else None,
            'kd_om': round(d.kd_om, 2) if d.do_duoc_kd else None,
            'kd_hang': round(d.kd_nha_san_xuat, 2) or None,
            'lk_thang': round(d.luy_ke_thang, 1),
            'mat_ngay': round(d.sl_mat, 1) if d.do_duoc_kd else None,
            'co_so_ngay': True,
        })
        return g

    # ==================================================================
    @api.model
    def map_data(self, plant_code=None, months=12, as_of=None):
        """Bổ sung khối SẢN LƯỢNG cấp nhà máy, đọc từ bảng kỳ."""
        kq = super().map_data(plant_code=plant_code, months=months,
                              as_of=as_of)
        nm = kq.get('plant')
        if not nm or not kq.get('summary'):
            return kq
        vt = self.search([('complete_code', '=', nm['code'])], limit=1)
        if not vt:
            return kq
        den = fields.Datetime.to_datetime(kq['as_of'])
        kq['summary']['san_luong'] = self._map_san_luong(vt, den.date())
        return kq

    @api.model
    def _map_san_luong(self, plant, ngay):
        """Sản lượng ngày và tháng, kèm ĐỘ PHỦ dữ liệu.

        Mỗi con số đi kèm số ngày nó dựa trên. Một tỷ lệ "đạt 71% kế
        hoạch" dựa trên 13 ngày trong một tháng 31 ngày là câu nói khác
        hẳn cùng con số ấy dựa trên đủ tháng — và chỉ có độ phủ mới phân
        biệt được hai câu.
        """
        U = self.env['eam.unit.day']
        P = self.env['eam.energy.period']
        A = self.env['eam.availability.day']
        ds = U.search([('plant_id', '=', plant.id), ('date', '=', ngay)])
        tong = U.tong_ngay(plant, ngay) if ds else {}
        ky = P.search([('plant_id', '=', plant.id),
                       ('loai_ky', '=', 'thang'),
                       ('tu_ngay', '<=', ngay),
                       ('den_ngay', '>=', ngay)], limit=1)
        # Khả dụng cấp nhà máy lấy từ SỔ KHẢ DỤNG, không tự cộng lại.
        a = A.search([('plant_id', '=', plant.id), ('date', '=', ngay)],
                     limit=1)
        return {
            'ngay': str(ngay),
            'co_so_ngay': bool(ds),
            'kwh_ngay': round(tong.get('san_luong') or 0, 1) if tong else None,
            'cf_ngay': (round(tong['he_so_cong_suat'], 2)
                        if tong.get('he_so_cong_suat') is not None else None),
            'kd_ngay': (round(tong['kd_san_luong'], 2)
                        if tong.get('kd_san_luong') is not None else None),
            'kd_om_ngay': (round(tong['kd_om'], 2)
                           if tong.get('kd_om') is not None else None),
            'kd_thoi_gian': round(a.kd_thoi_gian, 2) if a else None,
            'so_to_may_thieu': tong.get('so_chua_co_sl') if tong else None,
            # ----- tháng -----
            'thang': ky.nhan_ky if ky else None,
            'kwh_thang': round(ky.san_luong, 1) if ky else None,
            'cf_thang': round(ky.he_so_cong_suat, 2) if ky else None,
            'kd_thang': round(ky.kd_san_luong, 2) if ky else None,
            'mat_thang': round(ky.sl_mat, 1) if ky else None,
            'p50_thang': round(ky.p50, 1) if ky and ky.co_muc_tieu else None,
            'ty_le_p50': round(ky.ty_le_p50, 1) if ky and ky.co_muc_tieu else None,
            'dat_muc': ky.dat_muc if ky and ky.co_muc_tieu else None,
            'ngay_thieu_thang': ky.so_ngay_thieu if ky else None,
            'so_ngay_thang': ky.so_ngay if ky else None,
            'ly_do_khong_so': (ky.ly_do_khong_so if ky and not ky.co_muc_tieu
                               else None),
        }
