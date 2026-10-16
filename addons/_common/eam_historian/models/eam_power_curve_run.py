# -*- coding: utf-8 -*-
"""Phân tích đường cong công suất thực tế — theo IEC 61400-12-1.

Bốn chỗ làm ẩu thì ra số trông hợp lý mà sai
=============================================

**① Hiệu chỉnh mật độ không khí — và hiệu chỉnh CÁI GÌ.**
Công suất tỷ lệ với ρ·v³. Nhà máy ở cao nguyên 600 m có không khí
loãng hơn, cùng tốc độ gió cho ít công suất hơn — **không phải tua-bin
kém**. So thẳng với đường cong 1,225 kg/m³ là buộc tội nhà chế tạo một
cách oan.

Với tua-bin điều khiển góc cánh (pitch — gần như mọi tua-bin hiện đại),
IEC chuẩn hoá **TỐC ĐỘ GIÓ**: ``v_n = v · (ρ/ρ₀)^(1/3)``. Căn bậc ba
chứ không phải chia thẳng, vì công suất tỷ lệ với *lập phương* tốc độ.
Với tua-bin thất tốc (stall) thì ngược lại — chuẩn hoá công suất. Làm
nhầm chiều là sai cả đường cong.

**② Không có nhiệt độ thì KHÔNG hiệu chỉnh được — phải nói ra.**
Thiếu nhiệt độ môi trường mà vẫn gắn nhãn "đã hiệu chỉnh mật độ" là
nói dối. Ở đây nếu thiếu thì báo thẳng và kết quả ghi rõ là **chưa hiệu
chỉnh**, chứ không âm thầm dùng 1,225.

**③ Trung bình 10 PHÚT, không phải số đo tức thời.**
IEC yêu cầu trung bình 10 phút vì gió giật làm cặp (gió, công suất) tức
thời lệch pha: rotor có quán tính, công suất chạy sau tốc độ gió vài
giây. Ghép tức thời thì đám mây điểm loe ra và đường cong tính được
thấp hơn thực tế.

**④ Khoảng ít mẫu KHÔNG phải là kém hiệu suất.**
Một khoảng tốc độ gió chỉ có 2 mẫu mà lệch −30% là nhiễu, không phải
bằng chứng. IEC đòi tối thiểu 3 mẫu mỗi khoảng. Khoảng chưa đủ mẫu
phải hiện là **"chưa đủ mẫu"**, không được trộn vào phần kết luận —
trộn vào thì một tháng gió yếu sẽ "chứng minh" tua-bin hỏng.

Và điều quan trọng nhất: **bảo lãnh được quyết toán bằng AEP, không
phải bằng hình dạng đường cong.** So từng khoảng là để chẩn đoán xem
hỏng ở dải gió nào; so AEP mới là con số đi vào hợp đồng. Nên ở đây
tính cả hai và nói rõ cái nào dùng để làm gì.
"""
import html
import math
from datetime import timedelta

from odoo import _, api, fields, models

R_KHI = 287.05          # hằng số khí cho không khí khô, J/(kg·K)
RHO_CHUAN = 1.225       # kg/m³ — khí quyển chuẩn, mực nước biển, 15 °C
MAU_TOI_THIEU = 3       # IEC 61400-12-1: tối thiểu 3 mẫu mỗi khoảng
GIO_TOI_THIEU = 180     # IEC: tổng tối thiểu 180 giờ dữ liệu hợp lệ


def rho_tu_do_cao(h_m, t_k):
    """Mật độ không khí suy từ độ cao địa hình (khí quyển chuẩn ISA)."""
    p = 101325.0 * (1 - 2.25577e-5 * max(h_m, 0.0)) ** 5.25588
    return p / (R_KHI * t_k)


class EamPowerCurveRun(models.TransientModel):
    _name = 'eam.power.curve.run'
    _description = 'Phân tích đường cong công suất'

    location_id = fields.Many2one(
        'eam.location', string='Tua-bin', required=True,
        domain="[('location_type', '=', 'position')]")
    curve_id = fields.Many2one(
        'eam.power.curve', string='So với đường cong', required=True)
    date_from = fields.Datetime(
        string='Từ', required=True,
        default=lambda s: fields.Datetime.now() - timedelta(days=30))
    date_to = fields.Datetime(
        string='Đến', required=True, default=fields.Datetime.now)

    tag_power_id = fields.Many2one('eam.tag', string='Điểm đo công suất')
    tag_wind_id = fields.Many2one('eam.tag', string='Điểm đo tốc độ gió')
    tag_temp_id = fields.Many2one(
        'eam.tag', string='Nhiệt độ môi trường',
        help='Thiếu ô này thì KHÔNG hiệu chỉnh mật độ được, và kết quả '
             'sẽ ghi rõ là chưa hiệu chỉnh.')
    tag_press_id = fields.Many2one(
        'eam.tag', string='Áp suất khí quyển',
        help='Để trống thì suy áp suất từ độ cao địa hình.')
    elevation_m = fields.Float(
        string='Độ cao địa hình (m)', digits=(16, 0),
        help='Dùng khi không có điểm đo áp suất.')

    bin_width = fields.Float(string='Bề rộng khoảng (m/s)', default=0.5,
                             required=True)
    avg_seconds = fields.Integer(
        string='Trung bình (giây)', default=600, required=True,
        help='IEC yêu cầu 600 giây (10 phút). Ngắn hơn thì gió giật làm '
             'cặp (gió, công suất) lệch pha và đường cong tính được thấp '
             'hơn thực tế.')
    min_samples = fields.Integer(
        string='Mẫu tối thiểu mỗi khoảng', default=MAU_TOI_THIEU,
        required=True)
    bo_nghi = fields.Boolean(string='Bỏ số đo bị đánh dấu', default=True)
    bo_loai_tru = fields.Boolean(
        string='Bỏ khoảng không tính KPI', default=True,
        help='Loại bảo trì, tiết giảm, mất kết nối. BẮT BUỘC về mặt kỹ '
             'thuật: tua-bin bị tiết giảm vẫn có gió nhưng công suất bị '
             'ghìm, trộn vào thì đường cong tụt xuống một cách giả tạo.')

    ket_qua = fields.Html(string='Kết quả', compute='_compute_ket_qua',
                          sanitize=False)

    # ------------------------------------------------------------------
    @api.onchange('location_id')
    def _onchange_location(self):
        """Dò sẵn các điểm đo theo loại — khỏi bắt người dùng nhớ mã tag."""
        if not self.location_id:
            return
        T = self.env['eam.tag']

        def dau(loai, vt_ids):
            return T.search([('tag_type', '=', loai),
                             ('location_id', 'in', vt_ids),
                             ('is_virtual', '=', False)], limit=1)

        vt = self.location_id
        self.tag_power_id = dau('power', vt.ids)
        self.tag_wind_id = dau('wind_speed', vt.ids)
        # Nhiệt độ và áp suất MÔI TRƯỜNG thường chỉ có một bộ cho cả nhà
        # máy (cột khí tượng), không phải mỗi trụ một bộ — nên dò rộng
        # ra toàn nhà máy. Lấy nhầm nhiệt độ dầu hộp số ở đây thì mật độ
        # không khí tính ra vô nghĩa.
        nm = vt.plant_id
        if nm:
            trong = self.env['eam.location'].search(
                [('id', 'child_of', nm.id)]).ids
            tt = T.search([('tag_type', '=', 'temperature'),
                           ('location_id', 'in', trong),
                           ('is_virtual', '=', False),
                           ('code', 'ilike', 'AMB')], limit=1)
            self.tag_temp_id = tt
            self.tag_press_id = T.search(
                [('tag_type', '=', 'pressure'),
                 ('location_id', 'in', trong),
                 ('is_virtual', '=', False)], limit=1)

    # ------------------------------------------------------------------
    @api.depends('location_id', 'curve_id', 'date_from', 'date_to',
                 'tag_power_id', 'tag_wind_id', 'tag_temp_id',
                 'tag_press_id', 'elevation_m', 'bin_width', 'avg_seconds',
                 'min_samples', 'bo_nghi', 'bo_loai_tru')
    def _compute_ket_qua(self):
        for w in self:
            w.ket_qua = w._chay() if (w.tag_power_id and w.tag_wind_id
                                      and w.curve_id) else False

    def _cap_so_lieu(self):
        """Các cặp (gió, công suất) trung bình theo khoảng, đã lọc."""
        self.ensure_one()
        cr = self.env.cr
        ids = [self.tag_power_id.id, self.tag_wind_id.id]
        if self.tag_temp_id:
            ids.append(self.tag_temp_id.id)
        if self.tag_press_id:
            ids.append(self.tag_press_id.id)

        loc_q = ' AND quality = 0' if self.bo_nghi else ''
        sql = """
            SELECT to_timestamp(floor(extract(epoch FROM ts) / %s) * %s)
                       AT TIME ZONE 'UTC' AS buc,
                   avg(value) FILTER (WHERE tag_id = %s) AS p,
                   avg(value) FILTER (WHERE tag_id = %s) AS v,
                   stddev_samp(value) FILTER (WHERE tag_id = %s) AS v_sd,
                   avg(value) FILTER (WHERE tag_id = %s) AS t,
                   avg(value) FILTER (WHERE tag_id = %s) AS pr
            FROM eam_tag_reading
            WHERE tag_id = ANY(%s) AND ts >= %s AND ts < %s""" + loc_q + """
            GROUP BY 1 ORDER BY 1
        """
        cr.execute(sql, (
            self.avg_seconds, self.avg_seconds,
            self.tag_power_id.id, self.tag_wind_id.id, self.tag_wind_id.id,
            self.tag_temp_id.id or 0, self.tag_press_id.id or 0,
            ids, self.date_from, self.date_to))
        hang = cr.fetchall()

        bo = []
        if self.bo_loai_tru:
            bo = self.env['eam.data.exclusion'].khoang_ap_dung(
                [self.tag_power_id.id], self.date_from,
                self.date_to).get(self.tag_power_id.id) or []

        ra = []
        for buc, p, v, v_sd, t, pr in hang:
            if p is None or v is None:
                continue
            if any(a <= buc < b for a, b in bo):
                continue
            ra.append({'ts': buc, 'p': float(p), 'v': float(v),
                       'v_sd': float(v_sd) if v_sd is not None else None,
                       't': float(t) if t is not None else None,
                       'pr': float(pr) if pr is not None else None})
        return ra, len(hang)

    def _hieu_chinh(self, ds):
        """Chuẩn hoá tốc độ gió về mật độ quy chiếu. Trả (ds, ghi_chú)."""
        self.ensure_one()
        rho_ref = self.curve_id.air_density_ref or RHO_CHUAN
        co_t = any(d['t'] is not None for d in ds)
        if not co_t:
            # Không nhiệt độ thì KHÔNG hiệu chỉnh được. Gắn nhãn "đã
            # hiệu chỉnh" mà thực ra dùng 1,225 là nói dối.
            return ds, ('chưa hiệu chỉnh', _(
                'Không có điểm đo nhiệt độ môi trường nên KHÔNG hiệu '
                'chỉnh mật độ không khí được. Kết quả dưới đây là so '
                'sánh THÔ — nếu nhà máy không ở mực nước biển thì nó '
                'thiên lệch một cách có hệ thống.'))

        co_pr = any(d['pr'] is not None for d in ds)
        nguon = (_('đo áp suất trực tiếp') if co_pr
                 else _('suy áp suất từ độ cao %d m') % int(self.elevation_m))
        rho_ds = []
        for d in ds:
            if d['t'] is None:
                continue
            t_k = d['t'] + 273.15
            if t_k <= 0:
                continue
            if d['pr'] is not None:
                # Áp suất đo bằng hPa hay Pa? Dưới 2000 thì chắc chắn là
                # hPa — đoán theo độ lớn vì khai nhầm đơn vị ở đây làm
                # mật độ sai 100 lần mà vẫn ra một con số.
                pa = d['pr'] * 100.0 if d['pr'] < 2000 else d['pr']
                rho = pa / (R_KHI * t_k)
            else:
                rho = rho_tu_do_cao(self.elevation_m, t_k)
            d = dict(d)
            if self.curve_id.regulation == 'stall':
                # Thất tốc: chuẩn hoá CÔNG SUẤT, giữ nguyên tốc độ gió.
                d['p_n'] = d['p'] * (rho_ref / rho)
                d['v_n'] = d['v']
            else:
                # Pitch: chuẩn hoá TỐC ĐỘ GIÓ, căn bậc ba.
                d['v_n'] = d['v'] * (rho / rho_ref) ** (1.0 / 3.0)
                d['p_n'] = d['p']
            d['rho'] = rho
            rho_ds.append(d)
        tb = sum(d['rho'] for d in rho_ds) / len(rho_ds) if rho_ds else 0
        return rho_ds, ('đã hiệu chỉnh', _(
            'Đã hiệu chỉnh mật độ không khí (%(ng)s). Mật độ trung bình '
            '%(tb).4f kg/m³ so với quy chiếu %(ref).3f — %(ht)s.',
            ng=nguon, tb=tb, ref=rho_ref,
            ht=_('không khí loãng hơn quy chiếu') if tb < rho_ref
            else _('không khí đặc hơn quy chiếu')))

    def cuong_do_nhieu_dong(self, ds):
        """Cường độ nhiễu động trung bình (TI = σ/v̄) và cảnh báo thiên lệch.

        ĐÂY LÀ CHỖ PHƯƠNG PHÁP CHIA KHOẢNG THIÊN LỆCH CÓ HỆ THỐNG, và
        thiên theo hướng khiến tua-bin trông TỐT hơn thực tế.

        Đường cong công suất là hàm LỒI dưới công suất định mức (gần bậc
        ba). Trung bình của một hàm lồi lớn hơn hàm của trung bình. Nên
        lấy công suất trung bình 10 phút rồi so với đường cong tại *tốc
        độ gió trung bình* sẽ luôn cho ra "vượt cam kết" — và vượt càng
        nhiều khi gió càng động.

        Độ thiên xấp xỉ ``½ · P″(v) · σ²``. Ở vùng dốc nhất của đường
        cong, TI 15% có thể tạo ra vài chục phần trăm "vượt cam kết"
        hoàn toàn giả. IEC 61400-12-1 bản 2 có thủ tục chuẩn hoá nhiễu
        động cho đúng chuyện này.

        Chưa chuẩn hoá được thì ít nhất phải NÓI RA, chứ không để người
        đọc kết luận tua-bin tốt trong khi đó chỉ là hiệu ứng toán học.
        """
        co = [d for d in ds if d.get('v_sd') is not None and d['v'] > 0.5]
        if not co:
            return None, ''
        ti = sum(d['v_sd'] / d['v'] for d in co) / len(co) * 100.0
        if ti < 12:
            return ti, ''
        return ti, _(
            'Cường độ nhiễu động trung bình %(ti).1f%% — cao. Phương pháp '
            'chia khoảng THIÊN CAO một cách có hệ thống khi gió động, vì '
            'đường cong công suất là hàm lồi nên trung bình công suất lớn '
            'hơn công suất tại tốc độ gió trung bình. Con số "vượt cam '
            'kết" dưới đây có thể là hiệu ứng toán học chứ không phải '
            'tua-bin tốt. Muốn kết luận chắc thì cần chuẩn hoá nhiễu động '
            'theo IEC 61400-12-1 bản 2, hoặc so với một tua-bin khác cùng '
            'nhà máy trong cùng kỳ.', ti=ti)

    def _chia_khoang(self, ds):
        """Chia theo khoảng tốc độ gió — phương pháp bins của IEC."""
        self.ensure_one()
        bw = self.bin_width or 0.5
        kho = {}
        for d in ds:
            v = d.get('v_n', d['v'])
            k = math.floor(v / bw)
            kho.setdefault(k, []).append(d)
        ra = []
        for k in sorted(kho):
            nhom = kho[k]
            n = len(nhom)
            v_tb = sum(x.get('v_n', x['v']) for x in nhom) / n
            p_tb = sum(x.get('p_n', x['p']) for x in nhom) / n
            p_cam = self.curve_id.tra_cong_suat(v_tb)
            ra.append({
                'v_lo': k * bw, 'v_hi': (k + 1) * bw, 'v': v_tb,
                'p': p_tb, 'p_cam': p_cam, 'n': n,
                'du_mau': n >= self.min_samples,
                'lech': (None if not p_cam or p_cam <= 0
                         else (p_tb - p_cam) / p_cam * 100.0),
            })
        return ra

    def _aep(self, khoang):
        """AEP đo được vs cam kết, theo phân bố Rayleigh (IEC Annex).

        Đây mới là con số **bảo lãnh được quyết toán bằng**. So từng
        khoảng là để chẩn đoán hỏng ở dải gió nào; AEP mới là thứ đi vào
        hợp đồng.
        """
        self.ensure_one()
        du = [b for b in khoang if b['du_mau'] and b['p_cam'] is not None]
        if len(du) < 3:
            return []

        def ray(v, v_tb):
            return 1 - math.exp(-math.pi / 4.0 * (v / v_tb) ** 2)

        ra = []
        for v_tb in (5.0, 6.0, 7.0, 8.0, 9.0, 10.0):
            do = cam = 0.0
            for a, b in zip(du, du[1:]):
                f = ray(b['v'], v_tb) - ray(a['v'], v_tb)
                do += f * (a['p'] + b['p']) / 2.0
                cam += f * (a['p_cam'] + b['p_cam']) / 2.0
            ra.append({
                'v_tb': v_tb,
                'do': do * 8760 / 1000.0,      # MWh/năm
                'cam': cam * 8760 / 1000.0,
                'ty_le': (do / cam * 100.0) if cam > 0 else None,
            })
        return ra

    # ------------------------------------------------------------------
    # Kết xuất
    # ------------------------------------------------------------------
    def _chay(self):
        self.ensure_one()
        ds, tho = self._cap_so_lieu()
        if not ds:
            return ('<div style="padding:12px;color:#777">Không có cặp '
                    '(gió, công suất) nào trong khoảng này.</div>')

        ds, (trang_thai, ghi_chu) = self._hieu_chinh(ds)
        if not ds:
            return ('<div style="padding:12px;color:#777">Không tính được '
                    'mật độ không khí từ dữ liệu nhiệt độ hiện có.</div>')

        ti, canh_ti = self.cuong_do_nhieu_dong(ds)
        khoang = self._chia_khoang(ds)
        aep = self._aep(khoang)
        gio = len(ds) * self.avg_seconds / 3600.0
        du = [b for b in khoang if b['du_mau'] and b['lech'] is not None]

        # --- dải trạng thái ---
        mau_tt = '#2E7D5B' if trang_thai == 'đã hiệu chỉnh' else '#D98E3B'
        nen_tt = '#EAF5EE' if trang_thai == 'đã hiệu chỉnh' else '#FDF3E7'
        canh_gio = ''
        if gio < GIO_TOI_THIEU:
            canh_gio = (
                f'<div style="background:#FDECEA;border-left:3px solid '
                f'#B3261E;padding:9px 11px;margin-bottom:10px;font-size:12px">'
                f'Chỉ có <b>{gio:.0f} giờ</b> dữ liệu hợp lệ. IEC 61400-12-1 '
                f'đòi tối thiểu {GIO_TOI_THIEU} giờ — kết quả dưới đây để '
                f'<b>tham khảo</b>, chưa đủ làm căn cứ đòi bảo hành.</div>')

        ti_txt = ' · nhiễu động %.1f%%' % ti if ti is not None else ''
        canh_ti_html = ''
        if canh_ti:
            canh_ti_html = (
                f'<div style="background:#FDECEA;border-left:3px solid '
                f'#B3261E;padding:9px 11px;margin-bottom:10px;font-size:12px">'
                f'{html.escape(canh_ti)}</div>')

        dau = (
            f'<div style="background:{nen_tt};border-left:3px solid {mau_tt};'
            f'padding:9px 11px;margin-bottom:10px;font-size:12px">'
            f'<b>{html.escape(trang_thai.upper())}</b> · '
            f'{html.escape(ghi_chu)}</div>{canh_gio}{canh_ti_html}'
            f'<div style="font-size:12px;color:#777;margin-bottom:10px">'
            f'{len(ds):,} mẫu trung bình {self.avg_seconds // 60} phút '
            f'({gio:.0f} giờ) · {len(khoang)} khoảng gió · '
            f'{len(du)} khoảng đủ mẫu'
            f'{ti_txt}'
            f'</div>'.replace(',', '.'))

        # --- biểu đồ ---
        W, Hh, L, R, Tp, B = 900, 360, 46, 12, 12, 30
        v_max = max([b['v_hi'] for b in khoang] + [25.0])
        p_max = max([b['p'] for b in khoang]
                    + [p.power_kw for p in self.curve_id.point_ids] + [1.0])

        def X(v):
            return L + v / v_max * (W - L - R)

        def Y(p):
            return Tp + (1 - p / p_max) * (Hh - Tp - B)

        # Đám mây điểm: lấy mẫu thưa khi quá nhiều, vì 4.000 vòng tròn
        # SVG làm trình duyệt chậm thấy rõ mà hình không đẹp thêm.
        buoc = max(1, len(ds) // 1800)
        cham = ''.join(
            f'<circle cx="{X(d.get("v_n", d["v"])):.1f}" '
            f'cy="{Y(d.get("p_n", d["p"])):.1f}" r="1.3" '
            f'fill="#0E8C99" fill-opacity="0.18"/>'
            for d in ds[::buoc])

        cam_diem = sorted(self.curve_id.point_ids, key=lambda p: p.wind_speed)
        duong_cam = ' '.join(
            f'{X(p.wind_speed):.1f},{Y(p.power_kw):.1f}' for p in cam_diem)
        duong_do = ' '.join(
            f'{X(b["v"]):.1f},{Y(b["p"]):.1f}' for b in khoang if b['du_mau'])

        luoi = ''.join(
            f'<line x1="{L}" y1="{Y(p_max * k / 4):.1f}" x2="{W - R}" '
            f'y2="{Y(p_max * k / 4):.1f}" stroke="#EFE9DF"/>'
            f'<text x="{L - 6}" y="{Y(p_max * k / 4) + 3:.1f}" font-size="9" '
            f'fill="#999" text-anchor="end">{p_max * k / 4:.0f}</text>'
            for k in range(5))
        truc_x = ''.join(
            f'<text x="{X(v):.1f}" y="{Hh - 10}" font-size="9" fill="#999" '
            f'text-anchor="middle">{v:.0f}</text>'
            for v in range(0, int(v_max) + 1, 5))

        thua_txt = ' (hiện 1/%d)' % buoc if buoc > 1 else ''
        svg = (
            f'<svg viewBox="0 0 {W} {Hh}" style="width:100%;height:auto;'
            f'background:#FFFDF9;border:1px solid #E8E2D8;border-radius:8px">'
            f'{luoi}{cham}'
            f'<polyline fill="none" stroke="#9B4D6B" stroke-width="2" '
            f'stroke-dasharray="6 3" points="{duong_cam}"/>'
            f'<polyline fill="none" stroke="#0E8C99" stroke-width="2.2" '
            f'points="{duong_do}"/>{truc_x}'
            f'<text x="{L}" y="{Hh - 10}" font-size="9" fill="#999">m/s</text>'
            f'</svg>'
            f'<div style="font-size:11px;color:#777;margin:6px 0 12px">'
            f'<span style="color:#9B4D6B">▬ ▬</span> cam kết · '
            f'<span style="color:#0E8C99">▬▬</span> đo được (khoảng đủ mẫu) · '
            f'chấm mờ = mẫu {self.avg_seconds // 60} phút'
            f'{thua_txt}'
            f'</div>')

        # --- bảng khoảng ---
        hang = []
        for b in khoang:
            if b['p_cam'] is None:
                nx = ('<span style="color:#999">ngoài dải cam kết</span>')
            elif b['lech'] is None:
                # Công suất cam kết BẰNG 0 (dưới tốc độ khởi động, hoặc
                # trên tốc độ cắt) thì không có mẫu số để tính phần
                # trăm. Chia cho 0 hay quy ước 0% đều là bịa — nói
                # thẳng là không so được.
                nx = ('<span style="color:#999">cam kết 0 kW — '
                      'không tính được %</span>')
            elif not b['du_mau']:
                nx = (f'<span style="color:#999">chưa đủ mẫu '
                      f'({b["n"]}/{self.min_samples})</span>')
            else:
                mau = '#B3261E' if b['lech'] < -2 else (
                    '#2E7D5B' if b['lech'] > 2 else '#777')
                nx = (f'<span style="color:{mau};font-weight:600">'
                      f'{b["lech"]:+.1f}%</span>')
            # Tính sẵn ra biến: lồng f-string trong f-string với cùng
            # loại nháy chỉ hợp lệ từ Python 3.12, mà module này phải
            # chạy được trên bản cũ hơn.
            cam_txt = '—' if b['p_cam'] is None else '%.0f' % b['p_cam']
            hang.append(
                f'<tr style="border-top:1px solid #F0EAE0">'
                f'<td style="padding:4px 6px;font-size:12px">'
                f'{b["v_lo"]:.1f}–{b["v_hi"]:.1f}</td>'
                f'<td style="padding:4px 6px;text-align:right;font-size:12px;'
                f'color:#777">{b["n"]}</td>'
                f'<td style="padding:4px 6px;text-align:right;font-size:12px">'
                f'{b["p"]:.0f}</td>'
                f'<td style="padding:4px 6px;text-align:right;font-size:12px;'
                f'color:#777">{cam_txt}</td>'
                f'<td style="padding:4px 6px;text-align:right">{nx}</td></tr>')

        bang = (
            '<table style="width:100%;border-collapse:collapse">'
            '<tr style="color:#777;font-size:11px;text-align:left">'
            '<th style="padding:4px 6px">Khoảng gió (m/s)</th>'
            '<th style="padding:4px 6px;text-align:right">Mẫu</th>'
            '<th style="padding:4px 6px;text-align:right">Đo (kW)</th>'
            '<th style="padding:4px 6px;text-align:right">Cam kết (kW)</th>'
            '<th style="padding:4px 6px;text-align:right">Lệch</th></tr>'
            + ''.join(hang) + '</table>')

        # --- AEP ---
        if aep:
            ah = ''.join(
                f'<tr style="border-top:1px solid #F0EAE0">'
                f'<td style="padding:4px 6px;font-size:12px">{a["v_tb"]:.0f}'
                f' m/s</td>'
                f'<td style="padding:4px 6px;text-align:right;font-size:12px">'
                f'{a["do"]:,.0f}</td>'
                f'<td style="padding:4px 6px;text-align:right;font-size:12px;'
                f'color:#777">{a["cam"]:,.0f}</td>'
                f'<td style="padding:4px 6px;text-align:right;font-weight:600;'
                f'color:{"#B3261E" if (a["ty_le"] or 0) < 98 else "#2E7D5B"}">'
                f'{a["ty_le"]:.1f}%</td></tr>'.replace(',', '.')
                for a in aep)
            bang_aep = (
                '<div style="margin-top:16px"><b style="font-size:13px">'
                'Sản lượng năm (AEP) — con số bảo lãnh quyết toán bằng</b>'
                '<div style="font-size:11px;color:#777;margin:4px 0 6px">'
                'Tính theo phân bố gió Rayleigh ở từng tốc độ gió trung bình '
                'năm quy chiếu. So từng khoảng ở trên là để <b>chẩn đoán</b> '
                'hỏng ở dải gió nào; AEP mới là thứ đi vào hợp đồng.</div>'
                '<table style="width:100%;border-collapse:collapse">'
                '<tr style="color:#777;font-size:11px;text-align:left">'
                '<th style="padding:4px 6px">Gió TB năm</th>'
                '<th style="padding:4px 6px;text-align:right">Đo (MWh)</th>'
                '<th style="padding:4px 6px;text-align:right">Cam kết (MWh)'
                '</th><th style="padding:4px 6px;text-align:right">Tỷ lệ</th>'
                '</tr>' + ah + '</table></div>')
        else:
            bang_aep = (
                '<div style="margin-top:14px;font-size:12px;color:#777">'
                'Chưa tính được AEP — cần ít nhất 3 khoảng gió đủ mẫu nằm '
                'trong dải cam kết.</div>')

        return dau + svg + bang + bang_aep
