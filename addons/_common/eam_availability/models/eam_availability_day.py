# -*- coding: utf-8 -*-
"""Khả dụng theo ngày, và luỹ kế ba mức song song.

Luỹ kế KHÔNG lưu
----------------
Cùng luật đã dùng ở sản lượng theo bậc đo: luỹ kế tháng và năm tính lại
mỗi lần đọc. Lưu thì nhanh hơn, nhưng sửa một ngày giữa tháng là mọi
ngày sau nó sai cho tới khi có ai nhớ chạy lại — mà sẽ không ai nhớ.

Luỹ kế khả dụng KHÔNG phải trung bình các ngày
-----------------------------------------------
Đây là chỗ sai im lặng nhất của mọi báo cáo khả dụng. Trung bình cộng
phần trăm của ba mươi ngày cho mỗi ngày một trọng số bằng nhau, trong
khi một ngày lặng gió và một ngày gió mạnh đóng góp sản lượng khác nhau
cả chục lần.

Đúng là **cộng tử số rồi chia tổng mẫu số**: tổng sản lượng thực của
tháng chia tổng sản lượng đáng lẽ của tháng. Hai cách ra hai con số, và
cách sai luôn đẹp hơn vì ngày xấu bị pha loãng.
"""
import pytz

from datetime import datetime, time, timedelta

from odoo import _, api, fields, models


class EamAvailabilityDay(models.Model):
    _name = 'eam.availability.day'
    _description = 'Khả dụng theo ngày'
    _order = 'date desc, plant_id'
    _rec_name = 'display_name'

    plant_id = fields.Many2one(
        'eam.location', string='Nhà máy', required=True, index=True,
        domain="[('location_type', '=', 'plant')]", ondelete='cascade')
    date = fields.Date(string='Ngày', required=True, index=True)
    company_id = fields.Many2one(
        related='plant_id.company_id', store=True)

    # ----- Theo thời gian --------------------------------------------
    kd_thoi_gian = fields.Float(
        string='Khả dụng thời gian (%)', digits=(6, 2), readonly=True)
    gio_ky = fields.Float(string='Giờ-máy trong ngày', digits=(10, 2),
                          readonly=True, aggregator=False)
    gio_dung = fields.Float(string='Giờ dừng tính', digits=(10, 2),
                            readonly=True)
    gio_chua_quy = fields.Float(
        string='Giờ chưa quy trách nhiệm', digits=(10, 2), readonly=True)
    so_don_vi = fields.Integer(string='Số tổ máy', readonly=True,
                               aggregator=False)
    mau_so_doan = fields.Boolean(
        string='Mẫu số do hệ đoán', readonly=True,
        help='Nhà máy chưa khai số tổ máy nên hệ đếm vị trí thiết bị con '
             '— trong đó có cả trạm khí tượng, vốn không phát điện. Khai '
             'số thật vào rồi dựng lại.')
    so_may_kha_dung = fields.Float(
        string='Số tổ máy khả dụng bình quân', digits=(6, 2), readonly=True,
        aggregator=False,
        help='Giờ-máy sẵn sàng chia số giờ trong ngày. Hai mươi tư trên '
             'hai mươi tư tổ máy thì bằng đúng số tổ máy; có máy dừng nửa '
             'ngày thì ra số lẻ.')

    # ----- Theo sản lượng --------------------------------------------
    kd_san_luong = fields.Float(
        string='Khả dụng sản lượng (%)', digits=(6, 2), readonly=True)
    sl_that = fields.Float(string='Sản lượng thực (kWh)', digits=(16, 1),
                           readonly=True)
    sl_mat = fields.Float(string='Sản lượng mất (kWh)', digits=(16, 1),
                          readonly=True)
    sl_dang_le = fields.Float(string='Đáng lẽ phát (kWh)', digits=(16, 1),
                              readonly=True)
    nguon_sl = fields.Char(string='Sản lượng thực lấy từ đâu', readonly=True)
    do_duoc_sl = fields.Boolean(string='Đo được sản lượng', readonly=True)
    ly_do_chua_do = fields.Char(string='Vì sao chưa đo được', readonly=True)
    so_khoang_chua_tinh = fields.Integer(
        string='Khoảng dừng chưa tính kWh', readonly=True,
        help='Khoảng dừng trong ngày mà sản lượng mất còn để trống. Mẫu '
             'số thiếu đúng phần đó, nên khả dụng đang cao hơn sự thật.')

    # ----- Luỹ kế: TÍNH LẠI, không lưu -------------------------------
    luy_ke_thang = fields.Float(
        string='Luỹ kế tháng (%)', digits=(6, 2), compute='_compute_luy_ke')
    luy_ke_nam = fields.Float(
        string='Luỹ kế năm (%)', digits=(6, 2), compute='_compute_luy_ke')

    # ----- Hai chiều để LỌC ------------------------------------------
    #
    # Pane lọc bên trái chỉ nhận many2one, many2many và selection. Bảng
    # này gần như toàn số và cờ luận lý, nên hai câu hỏi hay dùng nhất
    # của màn — *"ngày nào tụt khả dụng"* và *"con số này có tin được
    # không"* — không lọc được. Hai trường dưới đây quy chúng về dạng
    # chọn, và LƯU để vào được domain.
    dai_kd = fields.Selection(
        [('cao', 'Từ 98% trở lên'),
         ('kha', '95% đến dưới 98%'),
         ('thap', '90% đến dưới 95%'),
         ('rat_thap', 'Dưới 90%')],
        string='Dải khả dụng (thời gian)', compute='_compute_loc',
        store=True, index=True,
        help='Mốc để QUÉT MẮT, không phải ngưỡng hợp đồng. Mỗi hợp đồng '
             'O&M cam kết một mức khác nhau; việc chấm theo cam kết nằm '
             'ở Hợp đồng ▸ Đánh giá & thanh toán, không ở đây.')
    can_cu = fields.Selection(
        [('du', 'Đủ căn cứ'),
         ('thieu_sl', 'Chưa đo được sản lượng'),
         ('con_khoang', 'Còn khoảng dừng chưa tính kWh'),
         ('chua_quy', 'Có giờ chưa quy trách nhiệm')],
        string='Căn cứ con số', compute='_compute_loc', store=True,
        index=True,
        help='Một dòng có thể thiếu nhiều thứ cùng lúc; ô này lấy cái '
             'NẶNG NHẤT. Thiếu sản lượng thì khả dụng theo sản lượng '
             'không tính được chút nào, nên nó đứng trên; còn giờ chưa '
             'quy trách nhiệm thì con số vẫn ra, chỉ chưa biết đổ cho ai.')

    @api.depends('kd_thoi_gian', 'do_duoc_sl', 'so_khoang_chua_tinh',
                 'gio_chua_quy')
    def _compute_loc(self):
        for r in self:
            kd = r.kd_thoi_gian or 0.0
            r.dai_kd = ('cao' if kd >= 98 else 'kha' if kd >= 95
                        else 'thap' if kd >= 90 else 'rat_thap')
            # Thứ tự NẶNG trước. Xếp ngược lại thì một ngày vừa thiếu
            # sản lượng vừa có giờ chưa quy sẽ hiện là "chưa quy" —
            # nghe như chỉ còn thiếu một chữ ký, trong khi thực ra nửa
            # bảng số chưa đo được.
            r.can_cu = ('thieu_sl' if not r.do_duoc_sl
                        else 'con_khoang' if r.so_khoang_chua_tinh
                        else 'chua_quy' if r.gio_chua_quy
                        else 'du')

    _uniq_ngay = models.Constraint(
        'UNIQUE(plant_id, date)',
        'Mỗi nhà máy chỉ có một dòng khả dụng cho một ngày.')

    @api.depends('plant_id', 'date')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '%s — %s' % (rec.plant_id.name or '',
                                            rec.date or '')

    def _compute_luy_ke(self):
        """Cộng tử số rồi chia tổng mẫu số — KHÔNG trung bình phần trăm."""
        for rec in self:
            if not (rec.plant_id and rec.date):
                rec.luy_ke_thang = rec.luy_ke_nam = 0.0
                continue

            def gom(tu_ngay):
                ds = self.search([
                    ('plant_id', '=', rec.plant_id.id),
                    ('date', '>=', tu_ngay), ('date', '<=', rec.date)])
                that = sum(ds.mapped('sl_that'))
                dang_le = sum(ds.mapped('sl_dang_le'))
                return 100.0 * that / dang_le if dang_le else 0.0

            rec.luy_ke_thang = gom(rec.date.replace(day=1))
            rec.luy_ke_nam = gom(rec.date.replace(month=1, day=1))

    # ==================================================================
    @api.model
    def dung_ngay(self, plant, ngay, so_don_vi=0):
        """Dựng hoặc cập nhật dòng khả dụng của một ngày."""
        from . import do_kha_dung_sl as sl
        from odoo.addons.eam_om_contract.models import do_kha_dung as tg

        # Biên ngày theo múi giờ NHÀ MÁY, không phải UTC.
        #
        # Trước đây chỗ này dựng mốc naive rồi để kho chuỗi thời gian
        # đọc như UTC — nghĩa là "ngày 15/10" của một nhà máy ở Việt Nam
        # thật ra là 07:00 ngày 15 tới 07:00 ngày 16 giờ địa phương. Bảy
        # tiếng của một ngày khác.
        #
        # Một mình nó thì chỉ lệch; đặt cạnh bảng hiệu suất tổ máy — vốn
        # dùng ngày địa phương — thì hai khối trên CÙNG MỘT TỜ nói về
        # hai khung hai mươi tư giờ khác nhau, mà không gì báo. Dòng
        # tổng không khớp dòng nhà máy, và người đọc không có cách nào
        # biết vì sao.
        mui = pytz.timezone(plant.mui_gio())
        dau = mui.localize(datetime.combine(ngay, time.min))
        tu = dau.astimezone(pytz.UTC).replace(tzinfo=None)
        den = ((dau + timedelta(days=1)).astimezone(pytz.UTC)
               .replace(tzinfo=None))
        doan = False
        if not so_don_vi:
            so_don_vi = plant.so_don_vi_kha_dung
        if not so_don_vi:
            # Đếm thay cho người khai là ĐOÁN: trạm khí tượng cũng là
            # một vị trí thiết bị nhưng không phát điện. Vẫn đếm để có
            # số chạy, nhưng cắm cờ để người đọc biết mẫu số chưa khai.
            so_don_vi = self.env['eam.location'].search_count([
                ('id', 'child_of', plant.id),
                ('location_type', '=', 'position')]) or 1
            doan = True

        t = tg.do_kha_dung_thoi_gian(self.env, plant, tu, den,
                                     so_don_vi=so_don_vi)
        s = sl.kha_dung_san_luong(self.env, plant, tu, den)

        vals = {
            'plant_id': plant.id, 'date': ngay,
            'kd_thoi_gian': t['gia_tri'],
            'gio_ky': t['mau_so'], 'gio_dung': t['gio_dung_tinh'],
            'gio_chua_quy': t['gio_chua_quy'], 'so_don_vi': t['so_don_vi'],
            'so_may_kha_dung': ((t['mau_so'] - t['gio_dung_tinh'])
                                / t['gio_ky']) if t['gio_ky'] else 0.0,
            'kd_san_luong': s['gia_tri'] if s['do_duoc'] else 0.0,
            'sl_that': s['sl_that'], 'sl_mat': s['sl_mat'],
            'sl_dang_le': s['sl_dang_le'], 'nguon_sl': s['nguon_sl'],
            'do_duoc_sl': s['do_duoc'], 'ly_do_chua_do': s['ly_do'],
            'so_khoang_chua_tinh': s['so_khoang_chua_tinh'],
            'mau_so_doan': doan,
        }
        cu = self.search([('plant_id', '=', plant.id),
                          ('date', '=', ngay)], limit=1)
        if cu:
            cu.write(vals)
            return cu
        return self.create(vals)

    @api.model
    def dung_khoang(self, plant, tu_ngay, den_ngay):
        """Dựng cả một dải ngày. Trả về số dòng đã dựng."""
        n = 0
        d = tu_ngay
        while d <= den_ngay:
            self.dung_ngay(plant, d)
            n += 1
            d += timedelta(days=1)
        return n
