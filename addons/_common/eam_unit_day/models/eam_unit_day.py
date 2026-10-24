# -*- coding: utf-8 -*-
"""Hiệu suất TỔ MÁY theo ngày — một dòng cho mỗi máy, mỗi ngày.

Khối chiếm nửa tờ báo cáo
--------------------------
Tờ báo cáo ngày của nhà máy điện gió dành nửa trang cho bảng hai mươi
sáu tua-bin; tờ điện mặt trời dành một khối tương tự cho mười chín bộ
nghịch lưu. Cùng một hình dạng: mỗi dòng một máy, mỗi cột một chỉ tiêu,
cuối bảng một dòng TỔNG.

Nên bảng này là **chung cho cả hai công nghệ**. Phần riêng — tốc độ gió
của tua-bin, giờ đồng bộ của bộ nghịch lưu — do gói ngành thêm vào.

Vì sao nó đáng có bảng riêng, không phải tính lúc in
-----------------------------------------------------
Con số cấp nhà máy trả lời *"hôm qua trại phát bao nhiêu"*. Bảng này
trả lời câu khác, và là câu người vận hành hỏi mỗi sáng: ***máy nào
đang kéo cả trại xuống***. Muốn trả lời thì phải so được giữa các máy,
xếp hạng được, và nhìn được xu hướng nhiều ngày — tính lúc in thì không
lọc, không cộng, không xếp hạng được.

HAI chỉ số khả dụng, và vì sao không gộp
-----------------------------------------
Trên tờ báo cáo thật, một tua-bin ghi khả dụng **38,08%** ở cột của nhà
máy và **79,68%** ở cột của nhà sản xuất. Khoảng cách ấy không phải lỗi
— nó là **phạm vi trách nhiệm**: hãng loại trừ những nguyên nhân không
thuộc về họ (lưới, bất khả kháng), ta thì tính hết vì ta mất sản lượng
thật.

Gộp hai cột thành một là xoá mất chỗ để cãi nhau với nhà thầu. Nên:
cột của ta **đo được** từ sổ dừng máy; cột của hãng **nhập vào** từ báo
cáo của họ; và hệ in luôn khoảng lệch, vì khoảng lệch mới là thứ đưa ra
bàn họp.

Dùng lại engine, không tính lần hai
------------------------------------
Khả dụng theo sản lượng gọi **đúng engine của sổ khả dụng nhà máy**, chỉ
đổi phạm vi từ nhà máy xuống tổ máy. Hai nơi cùng tính "sản lượng đáng
lẽ phát được" là hai nơi sớm muộn ra hai số.
"""
import logging
from datetime import datetime, time, timedelta

import pytz

from odoo import _, api, fields, models

from odoo.addons.eam_availability.models import do_kha_dung_sl as kd

_logger = logging.getLogger(__name__)


class EamUnitDay(models.Model):
    _name = 'eam.unit.day'
    _description = 'Hiệu suất tổ máy theo ngày'
    _order = 'date desc, location_code, id'
    _rec_name = 'display_name'

    location_id = fields.Many2one(
        'eam.location', string='Tổ máy', required=True, index=True,
        ondelete='cascade', domain="[('la_to_may', '=', True)]")
    location_code = fields.Char(related='location_id.code', store=True,
                                string='Mã')
    plant_id = fields.Many2one(
        'eam.location', related='location_id.plant_id', store=True,
        index=True, string='Nhà máy')
    date = fields.Date(string='Ngày', required=True, index=True)
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda s: s.env.company)

    # ----- Sản lượng --------------------------------------------------
    # LƯU ba số lẻ dù chỉ IN một. Hai mươi sáu dòng làm tròn tới 0,1
    # rồi mới cộng thì dòng TỔNG lệch tới ±1,3 kWh so với con số cấp
    # nhà máy — nhỏ, nhưng người đọc bấm máy tính lại là thấy ngay, và
    # một tờ báo cáo tự mâu thuẫn thì mất tin ở mọi dòng còn lại.
    san_luong = fields.Float(
        string='Sản lượng ngày (kWh)', digits=(16, 3))
    do_duoc_sl = fields.Boolean(string='Có số sản lượng')
    nguon_sl = fields.Char(string='Sản lượng lấy từ đâu', readonly=True)
    ly_do_sl = fields.Char(string='Vì sao chưa có sản lượng', readonly=True)

    luy_ke_thang = fields.Float(
        string='Luỹ kế tháng (kWh)', digits=(16, 3))
    so_ngay_thang = fields.Integer(
        string='Số ngày đã cộng',
        help='Luỹ kế cộng từ những ngày CÓ SỐ. Thiếu ngày thì con số nhỏ '
             'hơn thật — nên nó được in ra cạnh luỹ kế, chứ không giấu '
             'đi để tổng trông liền mạch.')
    luy_ke_nam = fields.Float(string='Luỹ kế năm (kWh)', digits=(16, 3))

    # ----- Hệ số công suất ---------------------------------------------
    cong_suat_kw = fields.Float(
        string='Công suất định mức (kW)', digits=(16, 1), readonly=True)
    nguon_cs = fields.Char(string='Công suất lấy từ đâu', readonly=True)
    he_so_cong_suat = fields.Float(
        string='Hệ số công suất (%)', digits=(16, 2), aggregator='avg')
    do_duoc_hs = fields.Boolean(string='Tính được hệ số')
    ly_do_hs = fields.Char(string='Vì sao chưa có hệ số', readonly=True)

    # ----- Khả dụng: HAI cột, cố ý ---------------------------------------
    kd_san_luong = fields.Float(
        string='Khả dụng theo sản lượng (%)', digits=(16, 2),
        aggregator='avg',
        help='CỦA TA đo: sản lượng thực ÷ (thực + mất). Tính HẾT mọi '
             'nguyên nhân, vì ta mất sản lượng thật bất kể lỗi của ai.')
    sl_that = fields.Float(string='Sản lượng thực (kWh)', digits=(16, 3))
    sl_mat = fields.Float(string='Sản lượng mất (kWh)', digits=(16, 3))
    do_duoc_kd = fields.Boolean(string='Đo được khả dụng')
    ly_do_kd = fields.Char(string='Vì sao chưa đo được', readonly=True)
    so_khoang = fields.Integer(string='Số khoảng dừng')
    so_khoang_chua_tinh = fields.Integer(
        string='Khoảng dừng chưa tính sản lượng mất',
        help='Khoảng dừng chưa quy ra kWh thì KHÔNG vào mẫu số. Khả dụng '
             'vì thế cao hơn thật — con số này là mức độ cao hơn.')

    sl_mat_om = fields.Float(
        string='Trong đó thuộc trách nhiệm nhà thầu (kWh)',
        digits=(16, 3),
        help='Phần sản lượng mất quy được cho hợp đồng O&M. Lưu riêng để '
             'HAI con số khả dụng cùng truy ngược về một bộ dữ liệu.')
    kd_om = fields.Float(
        string='Khả dụng phạm vi hợp đồng (%)', digits=(16, 2),
        compute='_compute_kd_om', store=True, aggregator='avg',
        help='Chỉ trừ phần mất thuộc trách nhiệm nhà thầu — ĐÂY là con '
             'số khớp với sổ khả dụng nhà máy và với kỳ hợp đồng O&M. '
             'Cột bên trái trừ HẾT mọi nguyên nhân, vì ta mất sản lượng '
             'thật bất kể lỗi của ai. Hai con số trả lời hai câu khác '
             'nhau, nên chúng KHÁC nhau là đúng — thiếu một trong hai '
             'mới là chỗ người ta cãi nhầm.')

    kd_nha_san_xuat = fields.Float(
        string='Khả dụng theo hãng (%)', digits=(16, 2), aggregator='avg',
        help='CON SỐ CỦA HÃNG, nhập từ báo cáo của họ — hệ KHÔNG tính ra '
             'được, vì phạm vi loại trừ là thoả thuận trong hợp đồng chứ '
             'không phải phép tính.')
    lech_kd = fields.Float(
        string='Lệch (điểm %)', digits=(16, 2), compute='_compute_lech',
        store=True, aggregator='avg',
        help='Hãng trừ đi ít nguyên nhân hơn ta, nên cột của họ thường '
             'cao hơn. Chính khoảng lệch này là thứ đưa ra bàn họp — '
             'gộp hai cột lại là xoá mất nó.')

    ghi_chu = fields.Char(string='Ghi chú')
    display_name = fields.Char(compute='_compute_display_name', store=True)

    _uniq = models.Constraint('unique(location_id, date)',
                              'Tổ máy này đã có dòng cho ngày đó rồi.')

    # ==================================================================
    @api.depends('location_id', 'date')
    def _compute_display_name(self):
        for r in self:
            r.display_name = '%s — %s' % (r.location_id.code or '',
                                          r.date or '')

    @api.depends('sl_that', 'sl_mat_om', 'do_duoc_kd')
    def _compute_kd_om(self):
        for r in self:
            m = r.sl_that + r.sl_mat_om
            r.kd_om = (100.0 * r.sl_that / m) if (r.do_duoc_kd and m) else 0.0

    @api.depends('kd_san_luong', 'kd_nha_san_xuat', 'do_duoc_kd')
    def _compute_lech(self):
        for r in self:
            r.lech_kd = (r.kd_nha_san_xuat - r.kd_san_luong
                         if r.do_duoc_kd and r.kd_nha_san_xuat else 0.0)

    # ==================================================================
    @api.model
    def _bien_ngay(self, plant, ngay):
        mui = pytz.timezone(plant.mui_gio() if hasattr(plant, 'mui_gio')
                            else 'Asia/Ho_Chi_Minh')
        dau = mui.localize(datetime.combine(ngay, time.min))
        return (dau.astimezone(pytz.UTC).replace(tzinfo=None),
                (dau + timedelta(days=1)).astimezone(pytz.UTC)
                .replace(tzinfo=None))

    @api.model
    def dung_ngay(self, plant, ngay, chi_om=False):
        """Dựng hoặc cập nhật dòng cho MỌI tổ máy đã khai của nhà máy.

        ``chi_om=False`` là cố ý: cột khả dụng trên tờ báo cáo tính HẾT
        mọi nguyên nhân mất sản lượng. Cột chỉ-tính-phần-nhà-thầu đã có
        nơi riêng của nó ở kỳ hợp đồng O&M — để hai nơi cùng ra một con
        số mang hai nghĩa là cách chắc chắn khiến cuộc họp cãi nhầm chỗ.
        """
        ds = plant.to_may()
        if not ds:
            return {'so_to_may': 0, 'ly_do': _(
                'Nhà máy chưa khai tổ máy nào. Mở hồ sơ nhà máy và bấm '
                '"Đánh dấu tổ máy theo điểm đo", hoặc tích tay — hệ '
                'KHÔNG đoán, vì đoán là đưa cả trạm khí tượng vào bảng.')}
        tu, den = self._bien_ngay(plant, ngay)
        ra = self.browse()
        for vt in ds:
            ra |= self._dung_mot(vt, ngay, tu, den, chi_om)
        return {'so_to_may': len(ra), 'ids': ra.ids,
                'canh_bao': plant.kiem_so_to_may()}

    def _dung_mot(self, vt, ngay, tu, den, chi_om):
        env = self.env
        d = self.search([('location_id', '=', vt.id),
                         ('date', '=', ngay)], limit=1)
        v = {'location_id': vt.id, 'date': ngay}

        # ----- sản lượng: dùng lại engine của sổ khả dụng -------------
        that, nguon = kd.san_luong_that(env, vt, tu, den)
        if that is None:
            v.update(san_luong=0.0, do_duoc_sl=False, nguon_sl=False,
                     ly_do_sl=_('tổ máy không có điểm đo điện năng nào có '
                                'số trong ngày này'))
        else:
            v.update(san_luong=that, do_duoc_sl=True, nguon_sl=nguon,
                     ly_do_sl=False)

        # ----- hệ số công suất ---------------------------------------
        cs, nguon_cs = vt.cong_suat_dinh_muc_kw()
        v['cong_suat_kw'] = cs or 0.0
        v['nguon_cs'] = nguon_cs or False
        gio = (den - tu).total_seconds() / 3600.0
        if not cs:
            v.update(he_so_cong_suat=0.0, do_duoc_hs=False, ly_do_hs=_(
                'chưa khai công suất định mức cho tổ máy — chia cho một '
                'con số đoán bừa thì ra tỷ lệ trông hợp lý và sai'))
        elif that is None:
            v.update(he_so_cong_suat=0.0, do_duoc_hs=False,
                     ly_do_hs=_('chưa có sản lượng thì chưa có tử số'))
        else:
            v.update(he_so_cong_suat=100.0 * that / (cs * gio),
                     do_duoc_hs=True, ly_do_hs=False)

        # ----- khả dụng theo sản lượng --------------------------------
        k = kd.kha_dung_san_luong(env, vt, tu, den, chi_om)
        mat_om, _d, _c = kd.san_luong_mat_ky(env, vt, tu, den, True)
        v['sl_mat_om'] = mat_om
        v.update(kd_san_luong=k['gia_tri'], sl_that=k['sl_that'],
                 sl_mat=k['sl_mat'], do_duoc_kd=k['do_duoc'],
                 ly_do_kd=k['ly_do'] or False,
                 so_khoang=k.get('so_khoang', 0),
                 so_khoang_chua_tinh=k.get('so_khoang_chua_tinh', 0))

        if d:
            # Cột của HÃNG là số nhập tay — dựng lại KHÔNG được xoá nó.
            d.write(v)
        else:
            d = self.create(v)
        d._tinh_luy_ke()
        return d

    def _tinh_luy_ke(self):
        """Luỹ kế tháng và năm, cộng từ những ngày CÓ SỐ.

        Ngày thiếu số không được cộng 0 vào — nhưng cũng không được giấu
        đi: số ngày đã cộng in ra ngay cạnh, để người đọc biết luỹ kế
        này dựa trên bao nhiêu ngày.
        """
        for r in self:
            dau_thang = r.date.replace(day=1)
            dau_nam = r.date.replace(month=1, day=1)
            thang = self.search([
                ('location_id', '=', r.location_id.id),
                ('do_duoc_sl', '=', True),
                ('date', '>=', dau_thang), ('date', '<=', r.date)])
            nam = self.search([
                ('location_id', '=', r.location_id.id),
                ('do_duoc_sl', '=', True),
                ('date', '>=', dau_nam), ('date', '<=', r.date)])
            r.luy_ke_thang = sum(thang.mapped('san_luong'))
            r.so_ngay_thang = len(thang)
            r.luy_ke_nam = sum(nam.mapped('san_luong'))

    # ==================================================================
    @api.model
    def tong_ngay(self, plant, ngay):
        """Dòng TỔNG cuối bảng — cộng được thì cộng, không thì nói rõ.

        Khả dụng toàn trại **không phải trung bình các phần trăm**: một
        tua-bin dừng cả ngày giữa mùa lặng gió và một tua-bin dừng cả
        ngày giữa mùa gió mạnh mất lượng điện khác hẳn nhau. Phải cộng
        tử số và cộng mẫu số rồi mới chia — đúng như luỹ kế khả dụng cấp
        nhà máy.
        """
        ds = self.search([('plant_id', '=', plant.id), ('date', '=', ngay)])
        if not ds:
            return {}
        do = ds.filtered('do_duoc_kd')
        that = sum(do.mapped('sl_that'))
        mat = sum(do.mapped('sl_mat'))
        mat_om = sum(do.mapped('sl_mat_om'))
        cs = sum(ds.filtered('do_duoc_hs').mapped('cong_suat_kw'))
        sl = sum(ds.filtered('do_duoc_sl').mapped('san_luong'))
        hang = ds.filtered(lambda x: x.kd_nha_san_xuat)
        return {
            'so_to_may': len(ds),
            'san_luong': sl,
            'so_chua_co_sl': len(ds) - len(ds.filtered('do_duoc_sl')),
            'luy_ke_thang': sum(ds.mapped('luy_ke_thang')),
            'he_so_cong_suat': (100.0 * sl / (cs * 24.0)) if cs else None,
            'kd_san_luong': (100.0 * that / (that + mat)
                             if (that + mat) else None),
            'so_chua_do_kd': len(ds) - len(do),
            # Con số KHỚP với sổ khả dụng nhà máy và với kỳ hợp đồng.
            'kd_om': (100.0 * that / (that + mat_om)
                      if (that + mat_om) else None),
            'sl_mat_om': mat_om,
            # Cột của hãng là số nhập, không có tử/mẫu để cộng — nên
            # trung bình là cách duy nhất, và phải nói rõ nó là trung
            # bình các phần trăm chứ không cùng loại với cột bên trái.
            'kd_nha_san_xuat': (sum(hang.mapped('kd_nha_san_xuat'))
                                / len(hang)) if hang else None,
            'so_co_so_hang': len(hang),
        }

    # ==================================================================
    @api.model
    def _cron_dung_hom_qua(self):
        hq = fields.Date.context_today(self) - timedelta(days=1)
        n = 0
        for nm in self.env['eam.location'].search(
                [('location_type', '=', 'plant')]):
            if nm.to_may():
                n += self.dung_ngay(nm, hq).get('so_to_may', 0)
        return {'da_dung': n, 'ngay': hq}
