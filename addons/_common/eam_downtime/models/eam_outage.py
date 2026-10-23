# -*- coding: utf-8 -*-
"""Hạch toán một lần dừng máy ra kWh và ra tiền."""
from odoo import _, api, fields, models
from odoo.exceptions import UserError

from . import san_luong_mat as sl


class EamOutage(models.Model):
    _inherit = 'eam.outage'

    group_id = fields.Many2one(
        related='category_id.group_id', string='Nhóm báo cáo', store=True,
        index=True)

    # ----- Sản lượng mất ---------------------------------------------
    nguon_mat = fields.Selection(
        sl.PHUONG_PHAP, string='Sản lượng mất lấy từ đâu', default='tay',
        required=True, tracking=True,
        help='Con số trong ô "sản lượng mất" đến từ đâu. Giữ lại vì một '
             'khoảng do người gõ tay và một khoảng do máy tính ra có sức '
             'nặng rất khác khi đem đi đòi nhà thầu.')
    mat_mong_doi = fields.Float(
        string='Máy đối chứng phát được (kWh)', digits=(16, 1),
        readonly=True, aggregator=False)
    mat_that = fields.Float(
        string='Máy này vẫn phát (kWh)', digits=(16, 1), readonly=True,
        aggregator=False,
        help='Dừng một phần thì máy vẫn phát. Phần đã vào công-tơ không '
             'được tính là mất.')
    so_doi_chung = fields.Integer(
        string='Số máy đối chứng', readonly=True, aggregator=False)
    ly_do_khong_tinh = fields.Char(
        string='Vì sao chưa tính được', readonly=True)

    # ----- Tiền -------------------------------------------------------
    gia_kwh = fields.Float(
        string='Giá áp dụng (/kWh)', digits=(16, 2), readonly=True,
        aggregator=False,
        help='Chụp lại giá tại thời điểm tính. Biểu giá mua bán điện '
             'trượt theo năm, nên tính lại sau hai năm mà không chụp giá '
             'thì con số cũ đổi mà không ai biết.')
    nguon_gia = fields.Char(string='Giá lấy từ đâu', readonly=True)

    # ==================================================================
    def action_tinh_san_luong_mat(self):
        """Tính kWh mất bằng máy đối chứng cho các khoảng đang chọn.

        KHÔNG tự chạy khi tạo bản ghi: nhiều khoảng dừng đã có số do
        người vận hành gõ từ báo cáo nhà thầu, và tự đè lên là xoá mất
        con số đã được hai bên nhìn.
        """
        de = tinh = 0
        for rec in self:
            if rec.nguon_mat in sl.CHUA_LAM:
                rec.ly_do_khong_tinh = sl.CHUA_LAM[rec.nguon_mat]
                de += 1
                continue
            kq = sl.san_luong_mat(self.env, rec)
            rec.mat_mong_doi = kq['kwh_mong_doi']
            rec.mat_that = kq['kwh_that']
            rec.so_doi_chung = kq['so_doi_chung']
            if kq['tinh_duoc']:
                rec.lost_mwh = kq['kwh'] / 1000.0
                rec.nguon_mat = 'doi_chung'
                rec.ly_do_khong_tinh = False
                tinh += 1
            else:
                # Giữ nguyên con số cũ. Không tính được KHÁC với bằng 0.
                rec.ly_do_khong_tinh = kq['ly_do']
                de += 1
        if len(self) == 1 and de and not tinh:
            raise UserError(_(
                'Chưa tính được: %s\n\nCon số cũ giữ nguyên — "không tính '
                'được" khác với "bằng 0".', self.ly_do_khong_tinh))
        return True

    # ------------------------------------------------------------------
    def _tim_gia_kwh(self, ngay):
        """Giá điện áp dụng tại một ngày, kèm chỗ lấy.

        Ưu tiên hợp đồng mua bán điện nếu phần đó có mặt; không thì lấy
        giá khai ngay trên nhà máy. Tra ``rp.ppa`` qua ``env`` chứ không
        khai phụ thuộc, để khách chỉ mua phần vận hành vẫn cài được.
        """
        self.ensure_one()
        nm = self.location_id.plant_id
        if 'rp.ppa' in self.env:
            ppa = self.env['rp.ppa'].sudo().search(
                [('project_id.plant_location_id', '=', nm.id)], limit=1)
            if ppa:
                for d in ppa.tariff_line_ids:
                    if d.date_from <= ngay <= (d.date_to or ngay):
                        return d.tariff, _('biểu giá %s, kỳ %s → %s',
                                           ppa.display_name, d.date_from,
                                           d.date_to)
                if ppa.tariff_base:
                    return ppa.tariff_base, _('giá gốc của %s',
                                              ppa.display_name)
        if nm.gia_dien_kwh:
            return nm.gia_dien_kwh, _('giá khai trên nhà máy %s', nm.code)
        return 0.0, ''

    def action_tinh_tien(self):
        """Quy kWh mất ra tiền theo biểu giá tại NGÀY XẢY RA."""
        for rec in self:
            if not rec.lost_mwh:
                continue
            gia, nguon = rec._tim_gia_kwh(rec.date_start.date())
            if not gia:
                rec.nguon_gia = _('chưa biết giá — nhà máy chưa có hợp '
                                  'đồng mua bán điện và cũng chưa khai '
                                  'giá; để trống còn hơn nhân với 0')
                continue
            rec.gia_kwh = gia
            rec.nguon_gia = nguon
            rec.lost_revenue = rec.lost_mwh * 1000.0 * gia
        return True
