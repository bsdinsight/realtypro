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

#: Mười hai cánh hoa gió, mỗi cánh 30 độ, bắt đầu từ Bắc.
SO_CANH = 12
TEN_HUONG = ['B', 'BĐB', 'ĐB', 'ĐĐB', 'Đ', 'ĐĐN', 'ĐN', 'NĐN',
             'N', 'NTN', 'TN', 'TTN']


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
    def bieu_do_ngay(self, buoc_phut=30):
        """Công suất toàn trại và tốc độ gió theo bước thời gian."""
        self.ensure_one()
        tp = self._tag_theo_ma('_P')
        ws = self._tag_theo_ma('_WS')
        if not tp:
            return {'do_duoc': False, 'ly_do': _(
                'nhà máy chưa có điểm đo công suất (*_P)')}
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
