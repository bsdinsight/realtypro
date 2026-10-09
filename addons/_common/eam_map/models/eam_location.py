# -*- coding: utf-8 -*-
import math

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models

# Bán kính Trái Đất trung bình, mét.
R_TRAI_DAT = 6371008.8


class EamLocation(models.Model):
    """Toạ độ và trạng thái hiện trường của vị trí chức năng.

    Vì sao toạ độ nằm ở module bản đồ chứ không ở lõi
    -------------------------------------------------
    "Vị trí hộp số bên trong tua-bin T07" là một vị trí chức năng hợp lệ
    nhưng **không có toạ độ nào có nghĩa** — nó nằm trong vỏ máy, cao
    120 m. Chỉ vị trí cấp nhà máy và cấp thiết bị mới cắm được lên bản
    đồ. Nhét kinh vĩ độ vào lõi là mời mọi người điền bừa cho đủ ô.
    """
    _inherit = 'eam.location'

    latitude = fields.Float(string='Vĩ độ', digits=(16, 7))
    longitude = fields.Float(string='Kinh độ', digits=(16, 7))
    elevation_m = fields.Float(string='Cao độ (m)', digits=(16, 1))
    has_coords = fields.Boolean(
        string='Có toạ độ', compute='_compute_has_coords', store=True,
        help='Lọc nhanh các vị trí chưa cắm được lên bản đồ.')

    # Thông số làm nên vòng ảnh hưởng dòng khí. Để ở vị trí chứ không ở
    # tài sản, vì vòng này là thuộc tính của CHỖ: thay máy khác cùng
    # hạng thì vòng không đổi.
    rotor_diameter_m = fields.Float(
        string='Đường kính rô-to (m)', digits=(16, 1),
        help='Dùng để vẽ vòng ảnh hưởng dòng khí. Khoảng cách giữa hai '
             'tua-bin tính theo BỘI SỐ của con số này, không tính theo '
             'mét tuyệt đối.')
    hub_height_m = fields.Float(string='Cao độ trục (m)', digits=(16, 1))
    rated_power_mw = fields.Float(string='Công suất đặt (MW)',
                                  digits=(16, 3))

    @api.depends('latitude', 'longitude')
    def _compute_has_coords(self):
        for l in self:
            l.has_coords = bool(l.latitude and l.longitude)

    # ------------------------------------------------------------------
    # Khoảng cách
    # ------------------------------------------------------------------
    @staticmethod
    def _khoang_cach_m(lat1, lon1, lat2, lon2):
        """Khoảng cách vòng lớn giữa hai điểm, mét (công thức haversine)."""
        p1, p2 = math.radians(lat1), math.radians(lat2)
        dp = p2 - p1
        dl = math.radians(lon2 - lon1)
        a = (math.sin(dp / 2) ** 2
             + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2)
        return 2 * R_TRAI_DAT * math.asin(min(1.0, math.sqrt(a)))

    # ------------------------------------------------------------------
    # Dữ liệu cho bản đồ
    # ------------------------------------------------------------------
    @api.model
    def _map_boi_so_gian_cach(self):
        """Bội số đường kính rô-to coi là đủ xa. Mặc định 5D."""
        v = self.env['ir.config_parameter'].sudo().get_param(
            'eam_map.wake_spacing_d')
        try:
            return float(v) if v else 5.0
        except ValueError:
            return 5.0

    def _map_lap_tai(self, moc):
        """Tài sản đang lắp TẠI MỐC đã cho, không phải 'hiện tại'.

        Không dùng ``current_location_id``: trường đó nghĩa là "chưa tháo
        ra", nên nó trả lời đúng mỗi câu hỏi về hôm nay. Bản đồ phải trả
        lời được cả câu *"lúc đó trong máy có con nào"* — và đó chính là
        câu đi đòi bảo hành ba năm sau.
        """
        self.ensure_one()
        I = self.env['eam.installation']
        d = moc.date()
        lap = I.search([('location_id', 'child_of', self.id),
                        ('date_install', '<=', d)])
        return lap.filtered(lambda x: not x.date_remove or x.date_remove >= d)

    def _map_trang_thai(self, moc):
        """Trạng thái tại MỐC, suy từ khoảng dừng đang mở lúc đó.

        Thứ tự quyết định:

        **① Chưa lắp máy thì không nói chuyện phát điện.** Vị trí chưa có
        tài sản nào lắp tại mốc là đang xây dựng, không phải "đang phát".
        Bỏ bước này thì bản đồ của một dự án chưa vận hành vẫn xanh rờn.

        **② Có khoảng dừng mở thì lấy loại có ĐỘ ƯU TIÊN NHỎ NHẤT**, đúng
        cơ chế phân xử của chuẩn — một máy có thể vừa hỏng vừa bị cắt
        giảm cùng lúc — chứ không lấy bản ghi mới nhất.

        **③ Không có khoảng mở thì coi như đang phát.** Đây là một GIẢ
        ĐỊNH, không phải sự thật: nó chỉ đúng khi sổ dừng máy được ghi
        đầy đủ. Độ bao phủ của sổ (bên eam_energy) là chỗ kiểm lại — một
        bản đồ toàn màu xanh đi kèm độ bao phủ 60% nghĩa là bản đồ đang
        nói dối.
        """
        self.ensure_one()
        O = self.env['eam.outage']
        mo = O.search([('location_id', 'child_of', self.id),
                       ('date_start', '<=', moc)], order='id desc')
        mo = mo.filtered(lambda o: not o.date_end or o.date_end >= moc)
        if not mo:
            lap = self._map_lap_tai(moc)
            if not lap:
                return 'not_installed', False
            # Dựng xong KHÁC chạy được. Giữa hai mốc đó là chạy thử và
            # nghiệm thu, có khi vài tháng. Thiếu bậc này thì mọi vị trí
            # vừa lắp máy đã hiện "đang phát" — bản đồ của một dự án
            # đang xây trông như đã vận hành xong.
            ngay = [a.date_commissioned
                    for a in lap.mapped('asset_id') if a.date_commissioned]
            # KHÔNG khai ngày vận hành thì KHÔNG suy. Thiếu dữ liệu mà
            # bịa ra một bậc trạng thái còn tệ hơn để trống.
            if ngay and min(ngay) > moc.date():
                return 'commissioning', False
            return 'running', False
        # Ưu tiên số NHỎ thắng.
        kd = min(mo, key=lambda o: (o.category_id.priority or 999, o.id))
        c = kd.category_id
        xl = getattr(c, 'energy_treatment', None)
        if getattr(c, 'is_data_gap', False):
            ma = 'no_data'
        elif xl == 'deemed':
            ma = 'curtailed'
        elif not c.counts_as_downtime:
            ma = 'standby'
        elif 'kế hoạch' in (c.name or '').lower():
            ma = 'maintenance'
        else:
            ma = 'down'
        return ma, kd

    def _map_payload_one(self, tu, den):
        """Gói dữ liệu một vị trí cho bản đồ. ``den`` là MỐC xem."""
        self.ensure_one()
        O = self.env['eam.outage']
        W = self.env.get('eam.work.order')

        ma, kd = self._map_trang_thai(den)

        # Giờ dừng trong cửa sổ: chỉ cộng khoảng CON, khoảng gốc của sự
        # cố lan nhiều máy bị loại để khỏi đếm đúp.
        ks = O.search([('location_id', 'child_of', self.id),
                       ('is_root_cause', '=', False),
                       ('date_start', '<=', den)])
        ks = ks.filtered(lambda o: not o.date_end or o.date_end >= tu)

        # Cộng phần GIAO với cửa sổ, KHÔNG cộng trọn thời lượng.
        #
        # Hai chỗ sai nếu lấy thẳng ``duration_hours``:
        # ① Khoảng bắt đầu trước cửa sổ bị cộng cả phần nằm ngoài — một
        #    lần dừng 40 ngày vắt qua ranh giới sẽ ăn hết khả dụng của
        #    kỳ mà phần lớn nó thuộc về kỳ trước.
        # ② Khoảng ĐANG MỞ có ``duration_hours`` tính tới BÂY GIỜ. Lùi
        #    mốc xem về quá khứ thì hiệu số âm, và khả dụng vọt lên trên
        #    100% — con số vô lý nhưng không màn hình nào chặn.
        gio_dung = 0.0
        for k in ks:
            if not k.counts_as_downtime:
                continue
            d1 = max(k.date_start, tu)
            d2 = min(k.date_end or den, den)
            if d2 > d1:
                gio_dung += (d2 - d1).total_seconds() / 3600.0
        gio_cua_so = (den - tu).total_seconds() / 3600.0
        kha_dung = (max(gio_cua_so - gio_dung, 0.0) / gio_cua_so * 100.0
                    if gio_cua_so else 0.0)

        mwh_mat = sum(ks.mapped('lost_mwh'))
        tien_mat = sum(ks.mapped('lost_revenue'))
        tien_te = ks.mapped('currency_id')

        lenh_mo = cho = 0
        ly_do_cho = []
        if W is not None:
            ls = W.search([('location_id', 'child_of', self.id),
                           ('state', 'not in',
                            ('done', 'closed', 'cancelled'))])
            lenh_mo = len(ls)
            dcho = ls.filtered('is_on_hold')
            cho = len(dcho)
            ly_do_cho = list({
                dict(W._fields['hold_reason'].selection).get(w.hold_reason)
                for w in dcho if w.hold_reason})

        ts = self._map_lap_tai(den).mapped('asset_id')

        # Số ngày bảo hành đếm từ MỐC XEM, không đếm từ hôm nay. Trường
        # ``warranty_days_left`` của tài sản luôn đo tới hôm nay — lùi
        # mốc về một ngày trong quá khứ mà vẫn dùng nó thì mọi cảnh báo
        # "sắp hết bảo hành" của ngày hôm đó biến mất sạch.
        ngay = den.date()
        bh = {a.id: (a.warranty_end - ngay).days
              for a in ts if a.warranty_end}
        bh_con = min(bh.values(), default=None)

        return {
            'id': self.id,
            'code': self.code,
            'path': self.complete_code,
            'name': self.name,
            'lat': self.latitude,
            'lon': self.longitude,
            'elev': self.elevation_m,
            'rotor_d': self.rotor_diameter_m,
            'hub_h': self.hub_height_m,
            'mw': self.rated_power_mw,
            'state': ma,
            'state_since': kd and kd.date_start and
            fields.Datetime.to_string(kd.date_start) or False,
            'state_hours': kd and round(
                (den - kd.date_start).total_seconds() / 3600.0, 1) or 0.0,
            'state_cat': kd and kd.category_id.name or False,
            'state_cat_code': kd and kd.category_id.code or False,
            'liability': kd and dict(
                kd._fields['liability'].selection).get(kd.liability) or False,
            # Vị trí CHƯA LẮP MÁY không có khả dụng để nói. Trả về 100%
            # thì một dự án đang xây hiện lên "khả dụng hoàn hảo" — con
            # số đẹp nhất trên màn hình lại là con số rỗng nghĩa nhất.
            # Vị trí ĐANG CHẠY THỬ cũng vậy: chưa tới ngày vận hành thì
            # chưa có cam kết khả dụng nào để đo.
            'avail': (None if ma in ('not_installed', 'commissioning')
                      else round(kha_dung, 2)),
            'down_hours': round(gio_dung, 1),
            'lost_mwh': round(mwh_mat, 1),
            'lost_money': round(tien_mat, 0),
            'outage_count': len(ks),
            'wo_open': lenh_mo,
            'wo_hold': cho,
            'wo_hold_why': ly_do_cho,
            'asset_count': len(ts),
            'assets': [{'code': a.code, 'name': a.name,
                        'serial': a.serial_no or '',
                        'cat': a.category_id.name or '',
                        'wdays': bh.get(a.id)}
                       for a in ts[:8]],
            'warranty_days': bh_con,
            'ccy': tien_te[:1].name or '',
            # Chỗ cho GÓI NGÀNH bơm thêm dòng vào popup mà lõi không cần
            # biết nội dung: mỗi dòng {label, value, warn}. Nhờ vậy bản
            # đồ dùng được cho cả nhà máy điện lẫn dây chuyền nhà xưởng
            # mà không phải khai trước mọi thứ có thể hiện.
            'extra': [],
            'erect_pct': None,
        }

    @api.model
    def map_data(self, plant_code=None, months=12, as_of=None):
        """Toàn bộ dữ liệu một lần gọi — bản đồ không gọi lại từng điểm.

        Gọi từng điểm thì 30 tua-bin thành 30 vòng truy vấn, và màn hình
        giật mỗi lần kéo bản đồ.

        ``as_of`` là MỐC XEM. Mặc định là bây giờ, nhưng phải đổi được:
        một dự án chưa tới ngày vận hành thương mại thì "bây giờ" chẳng
        có gì để xem, còn câu *"lúc xảy ra sự cố, trong máy có con hộp
        số nào"* chỉ trả lời được khi lùi được mốc. Mọi con số trên màn
        hình — trạng thái, tài sản đang lắp, khả dụng — đều tính theo
        mốc này, không trộn mốc nọ với mốc kia.
        """
        den = (fields.Datetime.to_datetime(as_of) if as_of
               else fields.Datetime.now())
        tu = den - relativedelta(months=months or 12)

        mien = [('has_coords', '=', True)]
        nha_may = False
        if plant_code:
            nha_may = self.search([('complete_code', '=', plant_code)],
                                  limit=1)
            if nha_may:
                mien.append(('id', 'child_of', nha_may.id))
        vt = self.search(mien)
        # Chỉ cắm vị trí THIẾT BỊ; vị trí cấu phần nằm trong vỏ máy.
        vt = vt.filtered(lambda l: l.location_type in ('plant', 'position'))
        cay = vt.filtered(lambda l: l.location_type == 'position')

        diem = [l._map_payload_one(tu, den) for l in cay]

        # ------------------------------------------------------------------
        # Cặp quá gần nhau.
        #
        # Vòng tròn một bán kính là MỘT PHÉP ĐƠN GIẢN HOÁ: dòng khí có
        # hướng, nên thực tế cần giãn 7–10D xuôi gió nhưng chỉ 3–5D ngang
        # gió. Không có hoa gió thì không tính đúng được. Con số ở đây
        # dùng để SOI CHỖ ĐÁNG NGỜ, không dùng để kết luận.
        # ------------------------------------------------------------------
        boi = self._map_boi_so_gian_cach()
        cap = []
        for i, a in enumerate(diem):
            for b in diem[i + 1:]:
                d = max(a['rotor_d'] or 0.0, b['rotor_d'] or 0.0)
                if not d:
                    continue
                kc = self._khoang_cach_m(a['lat'], a['lon'],
                                         b['lat'], b['lon'])
                if kc < boi * d:
                    cap.append({'a': a['code'], 'b': b['code'],
                                'm': round(kc), 'need': round(boi * d),
                                'd': round(kc / d, 2)})
        gan = {c for p in cap for c in (p['a'], p['b'])}
        for p in diem:
            p['too_close'] = p['code'] in gan

        tam = (nha_may and nha_may.has_coords
               and [nha_may.latitude, nha_may.longitude]) or (
            [sum(p['lat'] for p in diem) / len(diem),
             sum(p['lon'] for p in diem) / len(diem)] if diem else [0, 0])

        dem = {}
        for p in diem:
            dem[p['state']] = dem.get(p['state'], 0) + 1
        co_kd = [p for p in diem if p['avail'] is not None]
        mw_tong = sum(p['mw'] or 0.0 for p in diem)
        mw_phat = sum(p['mw'] or 0.0 for p in diem
                      if p['state'] == 'running')

        return {
            'plant': nha_may and {
                'code': nha_may.complete_code, 'name': nha_may.name,
                'lat': nha_may.latitude, 'lon': nha_may.longitude} or False,
            'center': tam,
            'points': diem,
            'pairs': cap,
            'spacing_d': boi,
            'months': months or 12,
            'as_of': fields.Datetime.to_string(den),
            'data_span': self._map_khoang_du_lieu(),
            'summary': {
                'n': len(diem),
                'by_state': dem,
                'mw_total': round(mw_tong, 2),
                'mw_running': round(mw_phat, 2),
                'avail': (round(sum(x['avail'] for x in co_kd)
                                / len(co_kd), 2) if co_kd else None),
                # Bình quân phải đi kèm MẪU SỐ. Lúc đang nghiệm thu, chỉ
                # vài vị trí đã vận hành nên bình quân có thể là 100% của
                # đúng MỘT máy — con số đúng về phép tính, lừa người đọc
                # về quy mô. Bày số vị trí ra cạnh nó.
                'avail_n': len(co_kd),
                'lost_mwh': round(sum(p['lost_mwh'] for p in diem), 1),
                'lost_money': round(sum(p['lost_money'] for p in diem)),
                'wo_open': sum(p['wo_open'] for p in diem),
                'wo_hold': sum(p['wo_hold'] for p in diem),
                'no_coords': self.search_count([
                    ('location_type', '=', 'position'),
                    ('has_coords', '=', False)]),
                'pairs': len(cap),
            },
            # Đồng tiền lấy từ chính các khoảng dừng, KHÔNG lấy của công
            # ty: doanh thu tổn thất tính theo giá hợp đồng mua bán điện
            # (ở đây là đô la Mỹ) trong khi sổ công ty ghi bằng đồng. Dán
            # nhãn đồng tiền của công ty lên một con số đô là sai gấp hơn
            # hai vạn lần, mà nhìn vẫn hợp lý.
            'currency': next((p['ccy'] for p in diem if p['ccy']),
                             self.env.company.currency_id.name or ''),
        }

    @api.model
    def _map_khoang_du_lieu(self):
        """Sổ dừng máy trải từ đâu tới đâu.

        Để màn hình nói được *"mốc anh đang xem không có dữ liệu, dữ liệu
        nằm ở quãng kia"* thay vì bày một bản đồ trống rồi để người dùng
        tự đoán là hỏng.
        """
        O = self.env['eam.outage']
        d = O.search([], order='date_start', limit=1)
        c = O.search([], order='date_start desc', limit=1)
        if not d:
            return False
        return {'from': fields.Datetime.to_string(d.date_start),
                'to': fields.Datetime.to_string(c.date_end or c.date_start)}

    def action_mo_ban_do(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'eam_map.plant_map',
            'name': _('Bản đồ — %s', self.name or ''),
            'params': {'plant_code': self.complete_code},
        }
