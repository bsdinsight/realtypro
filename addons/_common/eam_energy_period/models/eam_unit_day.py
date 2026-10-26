# -*- coding: utf-8 -*-
"""Sửa bảng tổ máy thì các kỳ phủ ngày ấy phải dựng lại NGAY.

Trước đây chỉ có cron dựng lại "các kỳ chạm vào hôm qua". Với dòng
chảy bình thường thì đủ: số của hôm qua chốt xong, đêm dựng lại ngày,
tuần, tháng, năm đang chạy. Nhưng O&M thì HIỆU CHỈNH SỐ QUÁ KHỨ suốt —
công-tơ đọc lại, một tổ máy bị loại khỏi phép tính, một ngày mất dữ
liệu được bù về sau. Những lần ấy cron không đụng tới, nên dòng ngày
cũ giữ nguyên con số đã chụp lúc dựng, còn dòng năm thì đêm nào cũng
được làm mới từ dữ liệu hiện tại.

Hậu quả đo được trên `aip` ngày 26/10/2026, nhà máy PV50:

    ngay   6.680.653      tuan   6.673.013
    thang  6.649.737      nam    6.641.990

Bốn câu trả lời khác nhau cho cùng một câu hỏi "nhà máy này phát bao
nhiêu", lệch 38.663 kWh. Không màn hình nào báo, vì mỗi con số tự nó
trông hoàn toàn bình thường.

Nay ghi/sửa/xoá một ngày là dựng lại ngay mọi bậc phủ ngày đó. Đắt hơn
một chút lúc ghi, đổi lấy việc bốn bậc không bao giờ nói khác nhau.
"""
from odoo import api, models


class EamUnitDay(models.Model):
    _inherit = 'eam.unit.day'

    @api.model_create_multi
    def create(self, vals_list):
        ds = super().create(vals_list)
        ds._dung_lai_ky()
        return ds

    def write(self, vals):
        # Chụp dải TRƯỚC khi ghi: đổi ngày hay đổi vị trí thì cả dải cũ
        # lẫn dải mới đều lệch, mà sau khi ghi thì dải cũ không còn dấu.
        cu = self._dai_anh_huong()
        ok = super().write(vals)
        self._dung_lai_ky(them=cu)
        return ok

    def unlink(self):
        cu = self._dai_anh_huong()
        ok = super().unlink()
        self.browse()._dung_lai_ky(them=cu)
        return ok

    # ------------------------------------------------------------------
    def _dai_anh_huong(self):
        """{id nhà máy: (ngày đầu, ngày cuối)} mà recordset này chạm vào."""
        dai = {}
        for r in self:
            if not r.plant_id or not r.date:
                continue
            tu, den = dai.get(r.plant_id.id, (r.date, r.date))
            dai[r.plant_id.id] = (min(tu, r.date), max(den, r.date))
        return dai

    def _dung_lai_ky(self, them=None):
        """Dựng lại kỳ cho các dải bị chạm.

        Gom thành MỘT dải cho mỗi nhà máy rồi dựng một lượt, chứ không
        dựng từng dòng: ghi một lô 400 ngày mà dựng 400 lần thì kỳ năm
        bị dựng lại 400 lần cho cùng một kết quả.

        `sudo` vì kỳ là số DẪN XUẤT: ai đã được quyền sửa bảng tổ máy
        thì đương nhiên được để con số dẫn xuất chạy theo. Bắt họ phải
        có thêm quyền ghi bảng kỳ chỉ tổ làm họ ghi được nguồn mà không
        cập nhật được tổng — tức là đẻ ra đúng cái lệch này.

        Đặt `bo_qua_dung_ky` trong context để tắt khi nạp dữ liệu lớn,
        rồi gọi `dung_dai` một lần ở cuối.
        """
        if self.env.context.get('bo_qua_dung_ky'):
            return
        dai = dict(them or {})
        for pid, (tu, den) in self._dai_anh_huong().items():
            if pid in dai:
                a, b = dai[pid]
                dai[pid] = (min(a, tu), max(b, den))
            else:
                dai[pid] = (tu, den)
        if not dai:
            return
        K = self.env['eam.energy.period'].sudo()
        L = self.env['eam.location'].sudo()
        for pid, (tu, den) in dai.items():
            K.dung_dai(L.browse(pid), tu, den)
