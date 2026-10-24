# -*- coding: utf-8 -*-
"""Sản lượng theo KỲ — ngày, tuần, tháng, năm — cho một hay nhiều nhà máy.

Vì sao là một bảng, không phải một màn hình tính lúc mở
--------------------------------------------------------
Câu "tháng này so tháng trước thế nào" và câu "ba nhà máy cộng lại được
bao nhiêu" đều cần cộng hàng nghìn dòng ngày. Tính lúc mở màn hình thì
mỗi lần mở là một lần quét lại, và không lọc được, không xếp hạng được,
không xuất được.

Quan trọng hơn: **bản đồ và các màn tổng quan sẽ đọc lại chính bảng
này**. Mỗi nơi tự cộng lấy là mỗi nơi một con số cho cùng một tháng —
và tới lúc lệch thì không ai biết bên nào mới.

Luỹ kế KHÔNG cộng ngày thiếu thành 0
-------------------------------------
Một kỳ thiếu ba ngày dữ liệu vẫn ra một con số dương trông bình thường,
chỉ nhỏ hơn thật. Nên mỗi dòng mang theo **số ngày có số** và **số ngày
thiếu**: con số đứng cạnh nhau thì người đọc tự biết nên tin tới đâu.

So với mục tiêu chỉ làm khi CÓ mục tiêu
----------------------------------------
Kỳ chưa khai mục tiêu thì cột so sánh để TRỐNG kèm lý do, chứ không ghi
0% — "đạt 0% kế hoạch" và "chưa ai khai kế hoạch" là hai chuyện khác
hẳn nhau, và chỉ một trong hai đáng báo động.
"""
import calendar
from datetime import date, timedelta

from odoo import _, api, fields, models

LOAI_KY = [
    ('ngay', 'Ngày'),
    ('tuan', 'Tuần'),
    ('thang', 'Tháng'),
    ('nam', 'Năm'),
]


class EamEnergyPeriod(models.Model):
    _name = 'eam.energy.period'
    _description = 'Sản lượng theo kỳ'
    _order = 'tu_ngay desc, plant_id'
    _rec_name = 'display_name'

    plant_id = fields.Many2one(
        'eam.location', string='Nhà máy', required=True, index=True,
        ondelete='cascade', domain="[('location_type', '=', 'plant')]")
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda s: s.env.company)
    loai_ky = fields.Selection(LOAI_KY, string='Loại kỳ', required=True,
                               index=True)
    tu_ngay = fields.Date(string='Từ ngày', required=True, index=True)
    den_ngay = fields.Date(string='Đến ngày', required=True, index=True)
    nhan_ky = fields.Char(string='Kỳ', readonly=True,
                          help='Nhãn đọc được: 2026-W42, 10/2026, 2026.')

    # ----- Sản lượng ---------------------------------------------------
    san_luong = fields.Float(string='Sản lượng (kWh)', digits=(16, 1))
    so_ngay = fields.Integer(string='Số ngày trong kỳ')
    so_ngay_co_so = fields.Integer(string='Số ngày CÓ số')
    so_ngay_thieu = fields.Integer(
        string='Số ngày thiếu',
        help='Ngày không có dòng nào trong bảng tổ máy. Luỹ kế KHÔNG cộng '
             'chúng thành 0 — nhưng con số vì thế nhỏ hơn thật, và đây là '
             'mức độ nhỏ hơn.')
    du_lieu_day = fields.Boolean(string='Đủ ngày', compute='_compute_day',
                                 store=True)

    cong_suat_dat_kw = fields.Float(string='Công suất đặt (kW)',
                                    digits=(16, 1))
    he_so_cong_suat = fields.Float(string='Hệ số công suất (%)',
                                   digits=(16, 2), aggregator='avg')

    # ----- Mất mát & khả dụng -------------------------------------------
    sl_mat = fields.Float(string='Sản lượng mất (kWh)', digits=(16, 1))
    kd_san_luong = fields.Float(string='Khả dụng theo sản lượng (%)',
                                digits=(16, 2), aggregator='avg')
    doanh_thu = fields.Monetary(string='Doanh thu', currency_field='currency_id')
    currency_id = fields.Many2one(
        'res.currency', default=lambda s: s.env.company.currency_id)

    # ----- So với mục tiêu ----------------------------------------------
    p50 = fields.Float(string='P50 (kWh)', digits=(16, 1))
    p75 = fields.Float(string='P75 (kWh)', digits=(16, 1))
    p90 = fields.Float(string='P90 (kWh)', digits=(16, 1))
    co_muc_tieu = fields.Boolean(string='Có mục tiêu')
    ly_do_khong_so = fields.Char(string='Vì sao chưa so được', readonly=True)
    ty_le_p50 = fields.Float(string='Đạt so với P50 (%)', digits=(16, 1),
                             aggregator='avg')
    dat_muc = fields.Selection(
        [('p50', 'Đạt P50'), ('p75', 'Đạt P75'), ('p90', 'Đạt P90'),
         ('duoi', 'Dưới P90')],
        string='Đạt tới mức', index=True,
        help='Mức CAO NHẤT đã vượt. "Dưới P90" là tín hiệu đáng báo động, '
             'không phải lỗi hiển thị.')

    display_name = fields.Char(compute='_compute_display_name', store=True)

    _uniq = models.Constraint(
        'unique(plant_id, loai_ky, tu_ngay, company_id)',
        'Nhà máy này đã có dòng cho kỳ đó rồi.')

    # ==================================================================
    @api.depends('plant_id', 'nhan_ky')
    def _compute_display_name(self):
        for r in self:
            r.display_name = '%s — %s' % (r.plant_id.name or '',
                                          r.nhan_ky or '')

    @api.depends('so_ngay', 'so_ngay_co_so')
    def _compute_day(self):
        for r in self:
            r.du_lieu_day = bool(r.so_ngay) and r.so_ngay_co_so >= r.so_ngay

    # ==================================================================
    @api.model
    def _bien_ky(self, loai, moc):
        """Mốc đầu và cuối của kỳ chứa ngày này, kèm nhãn đọc được."""
        if loai == 'ngay':
            return moc, moc, str(moc)
        if loai == 'tuan':
            d = moc - timedelta(days=moc.weekday())
            nam, tuan, _x = moc.isocalendar()
            return d, d + timedelta(days=6), '%d-W%02d' % (nam, tuan)
        if loai == 'thang':
            c = calendar.monthrange(moc.year, moc.month)[1]
            return (date(moc.year, moc.month, 1),
                    date(moc.year, moc.month, c),
                    '%02d/%d' % (moc.month, moc.year))
        return date(moc.year, 1, 1), date(moc.year, 12, 31), str(moc.year)

    @api.model
    def dung_ky(self, plant, loai, moc):
        """Dựng hoặc cập nhật một dòng kỳ, cộng từ BẢNG TỔ MÁY.

        Cộng từ bảng tổ máy chứ không đọc lại kho chuỗi thời gian: bảng
        tổ máy đã là nơi quyết định "ngày này nhà máy phát bao nhiêu",
        và đọc lại từ đầu là mở đường cho hai con số.
        """
        tu, den, nhan = self._bien_ky(loai, moc)
        U = self.env['eam.unit.day']
        ds = U.search([('plant_id', '=', plant.id),
                       ('date', '>=', tu), ('date', '<=', den)])
        co_ngay = len(set(ds.mapped('date')))
        so_ngay = (den - tu).days + 1
        sl = sum(ds.filtered('do_duoc_sl').mapped('san_luong'))
        mat = sum(ds.filtered('do_duoc_kd').mapped('sl_mat'))
        that = sum(ds.filtered('do_duoc_kd').mapped('sl_that'))
        cs = sum(plant.to_may().mapped('rated_power_mw')) * 1000.0
        gio = so_ngay * 24.0
        gia = plant.gia_dien_kwh or 0.0

        v = {
            'plant_id': plant.id, 'loai_ky': loai, 'tu_ngay': tu,
            'den_ngay': den, 'nhan_ky': nhan,
            'san_luong': sl, 'so_ngay': so_ngay, 'so_ngay_co_so': co_ngay,
            'so_ngay_thieu': max(so_ngay - co_ngay, 0),
            'cong_suat_dat_kw': cs,
            'he_so_cong_suat': (100.0 * sl / (cs * gio)) if cs else 0.0,
            'sl_mat': mat,
            'kd_san_luong': (100.0 * that / (that + mat)
                             if (that + mat) else 0.0),
            'doanh_thu': sl * gia,
        }
        v.update(self._so_muc_tieu(plant, loai, tu, den, sl))
        cu = self.search([('plant_id', '=', plant.id),
                          ('loai_ky', '=', loai),
                          ('tu_ngay', '=', tu)], limit=1)
        if cu:
            cu.write(v)
            return cu
        return self.create(v)

    @api.model
    def _so_muc_tieu(self, plant, loai, tu, den, san_luong):
        """Gộp mục tiêu của mọi tháng GIAO với kỳ.

        Kỳ tuần vắt qua hai tháng thì cộng phần của mỗi tháng theo tỷ lệ
        ngày — lấy trọn tháng là so một tuần với mục tiêu cả tháng, ra
        con số đạt 20% kế hoạch và ai cũng hoảng.
        """
        T = self.env['eam.energy.target']
        tong = {'p50': 0.0, 'p75': 0.0, 'p90': 0.0}
        thieu = []
        d = tu
        while d <= den:
            c = calendar.monthrange(d.year, d.month)[1]
            cuoi_thang = date(d.year, d.month, c)
            het = min(cuoi_thang, den)
            ngay_giao = (het - d).days + 1
            t = T.cua_thang(plant, d)
            if not t:
                thieu.append('%02d/%d' % (d.month, d.year))
            else:
                ty = ngay_giao / float(c)
                for m in ('p50', 'p75', 'p90'):
                    tong[m] += t[m] * ty
            d = het + timedelta(days=1)
        if thieu:
            return {
                'co_muc_tieu': False, 'p50': 0.0, 'p75': 0.0, 'p90': 0.0,
                'ty_le_p50': 0.0, 'dat_muc': False,
                'ly_do_khong_so': _('chưa khai mục tiêu cho tháng %s',
                                    ', '.join(thieu))}
        dat = 'duoi'
        for m in ('p50', 'p75', 'p90'):
            if tong[m] and san_luong >= tong[m]:
                dat = m
                break
        return {
            'co_muc_tieu': True, 'ly_do_khong_so': False,
            'p50': tong['p50'], 'p75': tong['p75'], 'p90': tong['p90'],
            'ty_le_p50': (100.0 * san_luong / tong['p50']) if tong['p50'] else 0.0,
            'dat_muc': dat,
        }

    # ==================================================================
    @api.model
    def dung_dai(self, plant, tu_ngay, den_ngay, cac_loai=None):
        """Dựng mọi kỳ chạm vào dải ngày này."""
        ra = self.browse()
        for loai in (cac_loai or ['ngay', 'tuan', 'thang', 'nam']):
            da = set()
            d = tu_ngay
            while d <= den_ngay:
                tu, den, _n = self._bien_ky(loai, d)
                if tu not in da:
                    da.add(tu)
                    ra |= self.dung_ky(plant, loai, d)
                d = den + timedelta(days=1)
        return ra

    @api.model
    def _cron_dung(self):
        """Dựng lại các kỳ đang chạm hôm qua, cho mọi nhà máy có tổ máy."""
        hq = fields.Date.context_today(self) - timedelta(days=1)
        n = 0
        for nm in self.env['eam.location'].search(
                [('location_type', '=', 'plant')]):
            if nm.to_may():
                n += len(self.dung_dai(nm, hq, hq))
        return {'da_dung': n, 'ngay': hq}

    # ==================================================================
    def action_xem_to_may(self):
        """Mở bảng tổ máy đúng kỳ này — để con số luôn lần ngược được."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Tổ máy — %s', self.nhan_ky),
            'res_model': 'eam.unit.day',
            'view_mode': 'list,graph,pivot,form',
            'domain': [('plant_id', '=', self.plant_id.id),
                       ('date', '>=', self.tu_ngay),
                       ('date', '<=', self.den_ngay)],
        }
