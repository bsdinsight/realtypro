# -*- coding: utf-8 -*-
"""Các KHỐI DỰNG SẴN của tờ báo cáo: bảng tổ máy, hoa gió, biểu đồ ngày.

Vì sao chúng không phải "dòng giá trị"
---------------------------------------
Phần lớn tờ báo cáo là *nhãn — con số*. Nhưng ba mảng chiếm nửa trang
lại không có hình dạng đó: bảng hai mươi sáu tua-bin, hoa gió, và đường
công suất trong ngày. Ép chúng thành dòng giá trị là hỏng cả hai phía.

Nên chúng là **khối**: hồ sơ cấu hình đặt một dòng đánh dấu chỗ, còn bản
in gọi xuống đây lấy dữ liệu. Thứ tự và vị trí vẫn do hồ sơ quyết — đổi
chỗ hoa gió không phải sửa mã.

Hướng gió KHÔNG trung bình số học được
---------------------------------------
Trung bình của 350° và 10° ra 180°, tức ngược hẳn hướng thật. Phải
trung bình VECTƠ. Kho chuỗi thời gian đã có sẵn phép ấy; ở đây dùng lại
đúng biểu thức đó thay vì viết lần hai.
"""
import logging
import math

from odoo import _, api, models

from odoo.addons.eam_historian.models.eam_historian import BANG

_logger = logging.getLogger(__name__)

#: MƯỜI SÁU cánh, mỗi cánh 22,5 độ — không phải mười hai.
#
# Bộ tên B / BĐB / ĐB / ĐĐB… là bộ MƯỜI SÁU ĐIỂM, tâm cách nhau 22,5°.
# Dùng nó cho mười hai cánh 30° thì mỗi nhãn lệch khỏi hướng thật tới
# bảy độ rưỡi và càng về sau càng lệch: cánh 30–60° (tức ĐÔNG BẮC) bị
# gọi là "BĐB". Hoa gió mười sáu cánh cũng là nếp của ngành.
SO_CANH = 16
TEN_HUONG = ['B', 'BĐB', 'ĐB', 'ĐĐB', 'Đ', 'ĐĐN', 'ĐN', 'NĐN',
             'N', 'NTN', 'TN', 'TTN', 'T', 'TTB', 'TB', 'BTB']


class EamDailyReport(models.Model):
    _inherit = 'eam.daily.report'

    # ==================================================================
    def bang_to_may(self):
        """Bảng từng tổ máy + dòng TỔNG, lấy thẳng từ bảng đã dựng."""
        self.ensure_one()
        U = self.env['eam.unit.day']
        ds = U.search([('plant_id', '=', self.plant_id.id),
                       ('date', '=', self.date)], order='location_code')
        return {'dong': ds, 'tong': U.tong_ngay(self.plant_id, self.date)}

    # ==================================================================
    def _tag_theo_ma(self, duoi):
        T = self.env['eam.tag']
        return T.search([('plant_id', '=', self.plant_id.id),
                         ('code', '=like', '%' + duoi)])

    def hoa_gio(self):
        """Tần suất và tốc độ gió theo mười hai hướng.

        Ghép hướng với tốc độ theo TỪNG MỐC thời gian rồi mới chia cánh:
        gộp riêng hai chuỗi rồi ghép sau là ghép tốc độ trung bình cả
        ngày vào hướng trung bình cả ngày — ra một bông hoa chỉ có một
        cánh, và cánh ấy không có thật.
        """
        self.ensure_one()
        wd = self._tag_theo_ma('_WD')
        ws = self._tag_theo_ma('_WS')
        if not wd or not ws:
            return {'do_duoc': False, 'ly_do': _(
                'nhà máy chưa có điểm đo hướng gió (*_WD) hoặc tốc độ '
                'gió (*_WS)')}
        tu, den = self._bien_ngay_utc()
        self.env.cr.execute("""
            WITH h AS (
                SELECT ts, mod(degrees(atan2(avg(sin(radians(value))),
                                             avg(cos(radians(value)))))
                              ::numeric + 360, 360) AS huong
                FROM {bang} WHERE tag_id = ANY(%s) AND ts >= %s AND ts < %s
                GROUP BY ts),
            t AS (
                SELECT ts, avg(value) AS toc
                FROM {bang} WHERE tag_id = ANY(%s) AND ts >= %s AND ts < %s
                GROUP BY ts)
            SELECT floor(h.huong / (360.0 / %s))::int AS canh,
                   count(*) AS n, avg(t.toc) AS toc, max(t.toc) AS toc_max
            FROM h JOIN t USING (ts)
            GROUP BY 1 ORDER BY 1
        """.format(bang=BANG), (wd.ids, tu, den, ws.ids, tu, den, SO_CANH))
        hang = self.env.cr.fetchall()
        if not hang:
            return {'do_duoc': False, 'ly_do': _(
                'không có số đo hướng và tốc độ gió cùng mốc trong ngày')}
        tong = sum(h[1] for h in hang)
        theo = {h[0]: h for h in hang}
        canh = []
        for i in range(SO_CANH):
            h = theo.get(i)
            goc = i * (360.0 / SO_CANH)
            # Toạ độ nhãn tính SẴN ở đây: bộ dựng bản in chạy biểu thức
            # trong hộp kín, không gọi được math. Nhét phép tính vào mẫu
            # in là để nó hỏng lúc in chứ không hỏng lúc nạp.
            canh.append({
                'i': i, 'ten': TEN_HUONG[i], 'goc': goc,
                'nx': 92.0 * math.sin(math.radians(goc)),
                'ny': -92.0 * math.cos(math.radians(goc)) + 3,
                'tan_suat': 100.0 * h[1] / tong if h else 0.0,
                'toc': float(h[2]) if h and h[2] is not None else 0.0,
                'toc_max': float(h[3]) if h and h[3] is not None else 0.0,
            })
        # Cánh dài nhất dùng làm thước vẽ. Lấy 1 khi mọi cánh bằng 0 để
        # khỏi chia cho 0 — bông hoa rỗng vẫn vẽ được cái khung.
        lon = max([c['tan_suat'] for c in canh]) or 1.0
        for c in canh:
            c['ty'] = c['tan_suat'] / lon
        return {'do_duoc': True, 'canh': canh, 'so_moc': tong,
                'troi_nhat': max(canh, key=lambda c: c['tan_suat'])}

    # ==================================================================
    def _tag_cong_suat(self):
        """Các điểm đo cộng lại ra CÔNG SUẤT TOÀN NHÀ MÁY — không trùng.

        Tra theo LOẠI ĐO chứ không theo đuôi mã: nhà máy điện gió đặt
        ``T01_P``, nhà máy điện mặt trời đặt ``PV50_P_01``, và một quy
        ước đặt tên viết cứng trong mã thì nhà máy thứ ba lại phá.

        Chỗ dễ sai là TRÙNG: điện mặt trời có cả điểm đo tổng ở cấp nhà
        máy lẫn mười sáu điểm đo từng bộ nghịch lưu. Cộng cả mười bảy ra
        gấp đôi — một đường cong trông vẫn mượt, chỉ cao gấp đôi. Nên có
        điểm đo ở CẤP NHÀ MÁY thì dùng riêng nó; không có mới cộng các
        điểm đo cấp máy.
        """
        self.ensure_one()
        tags = self.env['eam.tag'].search([
            ('plant_id', '=', self.plant_id.id), ('tag_type', '=', 'power')])
        o_nha_may = tags.filtered(lambda t: t.location_id == self.plant_id)
        return o_nha_may or tags

    def _so_to_may(self):
        """Số tổ máy của nhà máy — mẫu số để quy giờ-máy về giờ nhà máy.

        Ưu tiên con số NGƯỜI KHAI trên hồ sơ nhà máy; không có thì đếm
        vị trí đã gắn cờ tổ máy. Không có cả hai thì trả 0 để nơi gọi
        nói "chưa khai" — chia cho một con số đoán bừa ra một tỷ lệ
        trông hợp lý và sai.
        """
        self.ensure_one()
        nm = self.plant_id
        if getattr(nm, 'so_don_vi_kha_dung', 0):
            return nm.so_don_vi_kha_dung
        return self.env['eam.location'].search_count([
            ('id', 'child_of', nm.id), ('la_to_may', '=', True)])

    def bieu_do_ngay(self, buoc_phut=30):
        """Công suất toàn trại và tốc độ gió theo bước thời gian."""
        self.ensure_one()
        tp = self._tag_cong_suat()
        ws = self._tag_theo_ma('_WS')
        if not tp:
            return {'do_duoc': False, 'ly_do': _(
                'nhà máy chưa khai điểm đo nào loại "công suất"')}
        tu, den = self._bien_ngay_utc()
        b = buoc_phut * 60
        # HAI tầng gộp, và chúng KHÔNG đổi chỗ cho nhau được:
        #   1. theo từng MỐC: cộng công suất các tua-bin -> công suất trại;
        #   2. theo từng BỤC: lấy TRUNG BÌNH các tổng ấy.
        # Cộng dồn ở tầng hai thì ba mươi phút ra con số to gấp ba mươi
        # lần mà vẫn mang đơn vị kW — biểu đồ vẫn mượt, chỉ sai trục.
        self.env.cr.execute("""
            SELECT to_timestamp(floor(extract(epoch FROM ts) / %s) * %s)
                       AT TIME ZONE 'UTC' AS buc, avg(v)
            FROM (SELECT ts, sum(value) AS v FROM {bang}
                  WHERE tag_id = ANY(%s) AND ts >= %s AND ts < %s
                  GROUP BY ts) x
            GROUP BY 1 ORDER BY 1
        """.format(bang=BANG), (b, b, tp.ids, tu, den))
        cs = [(r[0], float(r[1])) for r in self.env.cr.fetchall()]

        gio = {}
        if ws:
            self.env.cr.execute("""
                SELECT to_timestamp(floor(extract(epoch FROM ts) / %s) * %s)
                           AT TIME ZONE 'UTC' AS buc, avg(value)
                FROM {bang} WHERE tag_id = ANY(%s) AND ts >= %s AND ts < %s
                GROUP BY 1 ORDER BY 1
            """.format(bang=BANG), (b, b, ws.ids, tu, den))
            gio = {r[0]: float(r[1]) for r in self.env.cr.fetchall()}

        import pytz
        mui = pytz.timezone(self._mui_gio())
        diem = []
        for ts, v in cs:
            tc = pytz.UTC.localize(ts).astimezone(mui)
            diem.append({'gio': tc.strftime('%H:%M'), 'cs': v,
                         'ws': gio.get(ts, 0.0)})
        if not diem:
            return {'do_duoc': False, 'ly_do': _(
                'không có số đo công suất nào trong ngày')}
        return {'do_duoc': True, 'diem': diem,
                'cs_max': max(d['cs'] for d in diem) or 1.0,
                'ws_max': max(d['ws'] for d in diem) or 1.0,
                'co_gio': bool(ws)}

    # ==================================================================
    def san_luong_gio(self, tu_gio=0, den_gio=24):
        """Điện năng từng GIỜ trong ngày, kèm số để vẽ cột.

        Khác biểu đồ ngày ở đơn vị, và khác biểu đồ ngày ở chỗ đó quan
        trọng. Biểu đồ ngày vẽ CÔNG SUẤT (kW) — ảnh chụp tại từng thời
        điểm. Tờ báo cáo của nhà máy lại đòi ĐIỆN NĂNG từng giờ (kWh) —
        tổng cộng dồn trong giờ ấy. Lấy trung bình công suất trong giờ
        rồi nhân một giờ thì ra điện năng; lấy TỔNG các số đo công suất
        trong giờ thì ra một con số gấp sáu lần mà vẫn mang đơn vị kWh.

        ``tu_gio``/``den_gio`` theo giờ TẠI NHÀ MÁY. Để mặc định 0–24 là
        cả ngày; tờ điện mặt trời chỉ in 06–18 vì ngoài khung đó không có
        nắng — nhưng khung ấy là của hồ sơ cấu hình, không viết cứng ở đây.
        """
        self.ensure_one()
        tp = self._tag_cong_suat()
        if not tp:
            return {'do_duoc': False, 'ly_do': _(
                'nhà máy chưa khai điểm đo nào loại "công suất"')}
        tu, den = self._bien_ngay_utc()
        self.env.cr.execute("""
            SELECT to_timestamp(floor(extract(epoch FROM ts) / 3600) * 3600)
                       AT TIME ZONE 'UTC' AS gio, avg(v)
            FROM (SELECT ts, sum(value) AS v FROM {bang}
                  WHERE tag_id = ANY(%s) AND ts >= %s AND ts < %s
                  GROUP BY ts) x
            GROUP BY 1 ORDER BY 1
        """.format(bang=BANG), (tp.ids, tu, den))
        hang = self.env.cr.fetchall()
        if not hang:
            return {'do_duoc': False, 'ly_do': _(
                'không có số đo công suất nào trong ngày')}

        import pytz
        mui = pytz.timezone(self._mui_gio())
        dong = []
        for ts, cs in hang:
            tc = pytz.UTC.localize(ts).astimezone(mui)
            if not (tu_gio <= tc.hour < den_gio):
                continue
            # Trung bình công suất trong giờ × 1 giờ = điện năng giờ ấy.
            dong.append({'gio': tc.strftime('%H:%M'), 'h': tc.hour,
                         'kwh': float(cs or 0.0)})
        if not dong:
            return {'do_duoc': False, 'ly_do': _(
                'không có số đo nào trong khung %(a)02d–%(b)02d giờ',
                a=tu_gio, b=den_gio)}
        return {'do_duoc': True, 'dong': dong,
                'tong': sum(d['kwh'] for d in dong),
                'dinh': max(d['kwh'] for d in dong) or 1.0,
                'khung': '%02d:00–%02d:00' % (tu_gio, den_gio),
                'ngoai_khung': len(hang) - len(dong)}

    # ==================================================================
    def gio_nguyen_nhan(self):
        """Giờ dừng tách theo từng LOẠI THỜI GIAN, không gộp thành nhóm.

        Sổ dừng máy đã có sẵn phép cắt khoảng theo biên ngày — khoảng
        dừng vắt qua nửa đêm phải chia cho hai ngày. Gọi lại đúng phép
        ấy với trục ``loai`` thay vì chép sang đây, vì chép là hai nơi
        cùng phải nhớ cắt, và nơi quên sẽ im lặng.
        """
        self.ensure_one()
        tu, den = self._bien_ngay_utc()
        theo = self.plant_id.gio_theo_nhom(tu, den, theo='loai')
        dong = [{'ten': k, **v} for k, v in theo.items()]
        dong.sort(key=lambda d: -d['gio'])
        return {
            'do_duoc': True, 'dong': dong,
            'tong_gio': sum(d['gio'] for d in dong),
            'tong_kwh': sum(d['kwh'] for d in dong),
            'tong_so': sum(d['so'] for d in dong),
            # Giá điện chưa khai thì KHÔNG in cột tiền, thay vì in một
            # tổng nhỏ hơn thật mà trông như đã tính xong.
            'co_tien': not any(d.get('chua_tien') for d in dong)
                       and any(d['tien'] for d in dong),
        }

    # ==================================================================
    def bang_inverter(self):
        """Bảng tổ máy XOAY NGANG: chỉ tiêu làm hàng, từng bộ làm cột.

        Tờ báo cáo của nhà máy điện mặt trời xếp ngược với bảng tua-bin:
        bảy chỉ tiêu nằm dọc, mười chín bộ nghịch lưu nằm ngang. Không
        phải chuyện thẩm mỹ — mười chín dòng bảy cột thì mắt phải quét
        dọc để so các bộ với nhau, còn bảy dòng mười chín cột thì một
        hàng là một chỉ tiêu và máy nào lệch đàn lộ ra ngay.

        Cột TRUNG BÌNH tính trên những bộ CÓ SỐ của chính chỉ tiêu đó,
        không phải trên tổng số bộ: hai bộ mất tín hiệu làm mẫu số to
        lên mà tử số không đổi, và trung bình tụt xuống vì một lý do
        chẳng liên quan gì tới việc phát điện.
        """
        self.ensure_one()
        import pytz
        mui = pytz.timezone(self._mui_gio())
        ds = self.env['eam.unit.day'].search(
            [('plant_id', '=', self.plant_id.id), ('date', '=', self.date)],
            order='location_code')
        if not ds:
            return {'do_duoc': False, 'ly_do': _(
                'chưa dựng sổ ngày tổ máy cho ngày này')}

        def gio(ts):
            if not ts:
                return None
            return pytz.UTC.localize(ts).astimezone(mui)

        def phut(ts):
            t = gio(ts)
            return None if t is None else t.hour * 60 + t.minute

        def chu_gio(p):
            return '—' if p is None else '%02d:%02d' % (p // 60, p % 60)

        chi_tieu = [
            ('Synchronization time (hh:mm)', 'gio',
             [phut(d.moc_dong_bo) for d in ds]),
            ('De-synchronization time (hh:mm)', 'gio',
             [phut(d.moc_ngat) for d in ds]),
            ('h nominal (nominal operating hours)', '%.2f',
             [d.gio_danh_nghia or None for d in ds]),
            ('Max Peak DC, MW', '%.3f',
             [(d.dinh_dc / 1000.0) if d.do_duoc_dc else None for d in ds]),
            ('Max Peak AC, MW', '%.3f',
             [(d.dinh_ac / 1000.0) or None for d in ds]),
            ('Average efficiency (%)', '%.2f',
             [d.hieu_suat_bd if d.do_duoc_dc else None for d in ds]),
            ('Energy Output Inverter (MWh)', '%.3f',
             [(d.san_luong / 1000.0) if d.do_duoc_sl else None for d in ds]),
        ]
        hang = []
        for ten, dang, gt in chi_tieu:
            co = [x for x in gt if x is not None]
            tb = (sum(co) / len(co)) if co else None
            if dang == 'gio':
                o = [chu_gio(x) for x in gt]
                tbc = chu_gio(int(round(tb)) if tb is not None else None)
            else:
                o = ['—' if x is None else dang % x for x in gt]
                tbc = '—' if tb is None else dang % tb
            hang.append({'ten': ten, 'tb': tbc, 'o': o,
                         'thieu': len(gt) - len(co)})
        return {
            'do_duoc': True, 'hang': hang,
            'cot': [d.location_code or '' for d in ds],
            'so_may': len(ds),
            'thieu_dc': len([d for d in ds if not d.do_duoc_dc]),
            'ly_do_dc': next((d.ly_do_dc for d in ds if d.ly_do_dc), ''),
        }

    # ==================================================================
    #: Công-tơ ĐIỆN NĂNG. Đồng hồ giờ máy chạy cũng là eam.meter nhưng
    #: không thuộc về tờ giao nhận: nhà máy mười hai tua-bin có mười hai
    #: đồng hồ giờ, in lẫn vào đây thì bảng giao nhận dài gấp ba và
    #: không dòng nào trong đó liên quan tới sản lượng bán được.
    LOAI_DIEN_NANG = ('other', 'production_mwh')

    def cong_to_giao_nhan(self):
        """Bảng số đọc công-tơ: hôm qua · hôm nay · chênh.

        Đây là chỗ DUY NHẤT trên tờ báo cáo có chứng từ đi kèm. Mọi con
        số khác suy ra từ chuỗi số đo; riêng dòng này là hiệu hai lần
        đọc đồng hồ, và nó là thứ đem đối chiếu với hoá đơn.

        Thiếu một trong hai lần đọc thì KHÔNG tính chênh. Lấy số đọc gần
        nhất thay cho số đọc hôm qua là âm thầm cộng sản lượng của nhiều
        ngày vào một ngày — vẫn ra số dương, vẫn hợp lý, và chỉ lộ khi
        cộng cả tháng lại thấy vượt.
        """
        self.ensure_one()
        from datetime import timedelta
        M = self.env['eam.meter']
        R = self.env['eam.meter.reading']
        ds = M.search([('location_id', 'child_of', self.plant_id.id),
                       ('meter_type', 'in', self.LOAI_DIEN_NANG)],
                      order='location_code')
        if not ds:
            return {'do_duoc': False, 'ly_do': _(
                'nhà máy chưa khai công-tơ điện năng nào — mười hai đồng '
                'hồ giờ máy chạy không thuộc bảng giao nhận')}
        hom_qua = self.date - timedelta(days=1)
        # KHÔNG có dòng tổng. Bảng này gồm công-tơ XUẤT, công-tơ NHẬN
        # và công-tơ tự dùng — ba chiều khác nhau. Cộng chúng lại ra một
        # con số không mang nghĩa gì, mà vẫn là một con số đẹp nằm cuối
        # bảng, nên sớm muộn sẽ có người trích dẫn nó.
        dong = []
        for m in ds:
            a = R.search([('meter_id', '=', m.id),
                          ('date', '=', hom_qua)], limit=1)
            b = R.search([('meter_id', '=', m.id),
                          ('date', '=', self.date)], limit=1)
            chenh = None
            vi = ''
            if not b:
                vi = _('chưa có số đọc hôm nay')
            elif not a:
                vi = _('chưa có số đọc hôm qua — không tính chênh được')
            elif b.is_reset:
                vi = _('đồng hồ đã được thay / quay vòng trong ngày')
            else:
                chenh = (b.effective_value or 0.0) - (a.effective_value or 0.0)
                if chenh < 0:
                    vi = _('số đọc hôm nay NHỎ HƠN hôm qua')
                    chenh = None

            dong.append({
                'ten': m.location_id.name or m.display_name,
                'dv': m.uom_label or 'kWh',
                'hq': a.effective_value if a else None,
                'hn': b.effective_value if b else None,
                'ra': chenh, 'vi': vi,
            })
        return {'do_duoc': True, 'dong': dong,
                'so_thieu': len([d for d in dong if d['ra'] is None])}
