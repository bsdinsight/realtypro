# -*- coding: utf-8 -*-
"""Nền dựng giao diện — port từ bản thiết kế Claude Design sang Python.

Bản thiết kế gốc là component chạy trên trình duyệt: biểu đồ tính bằng
JavaScript rồi React vẽ ra. Odoo Community không có sẵn tầng đó, và cả
bộ RealtyPro đang theo lối **sinh SVG từ máy chủ rồi nhúng vào form**
(xem re_loan_dashboard, re_cashflow). Vì vậy toàn bộ phép tính toạ độ
được chuyển sang Python ở đây, giữ nguyên từng con số của thiết kế:
cùng khung nhìn, cùng lề, cùng bước chia lưới.

Không phụ thuộc thư viện biểu đồ, không gọi CDN — đúng ràng buộc đã
chốt trong tài liệu đề xuất.
"""
import math
from datetime import date

from markupsafe import Markup, escape

# Bảng màu thương hiệu RealtyPro
C = {
    'navy': '#0F2C3F',
    'teal': '#0E8C99',
    'amber': '#F2A93B',
    'red': '#D64545',
    'green': '#2E9E5B',
    'gray': '#9AA7AE',
    'ink': '#3E5A68',
    'muted': '#5E7683',
    'faint': '#7B8F99',
    'line': '#D3DBDF',
    'line2': '#E4EAED',
    'bg': '#E9EDEF',
}

TONE = {'ok': C['green'], 'warn': C['amber'], 'bad': C['red'],
        'na': C['gray']}

TONE_TEXT = {'ok': 'Tốt', 'warn': 'Cảnh báo', 'bad': 'Nguy hiểm',
             'na': 'Chưa đủ dữ liệu'}


def tone(kind):
    return TONE.get(kind, C['gray'])


def _vn(n):
    """Số nguyên kiểu Việt Nam: phân cách hàng nghìn bằng dấu chấm."""
    return '{:,.0f}'.format(n).replace(',', '.')


def fmt(v):
    """Số tiền rút gọn: '1.234 tỷ' · '86,5 tỷ' · '450 tr'.

    Giữ đúng quy tắc của thiết kế: từ 100 tỷ trở lên bỏ phần thập phân
    (số đã đủ lớn, thêm số lẻ chỉ làm rối), dưới đó giữ một chữ số.
    """
    if v is None:
        return '—'
    sign = '-' if v < 0 else ''
    a = abs(v)
    if a >= 1e9:
        x = a / 1e9
        if x >= 100:
            return sign + _vn(round(x)) + ' tỷ'
        return sign + ('%.1f' % x).replace('.', ',') + ' tỷ'
    if a >= 1e6:
        return sign + _vn(round(a / 1e6)) + ' tr'
    if a == 0:
        return '0'
    return sign + _vn(round(a))


def full(v):
    """Số đầy đủ cho tooltip — hiện khi rê chuột."""
    if v is None:
        return 'Chưa đủ dữ liệu'
    return _vn(round(v)) + ' ₫'


def num(v, digits=2):
    if v is None:
        return '—'
    return ('%.*f' % (digits, v)).replace('.', ',')


def pct(v, digits=1):
    if v is None:
        return '—'
    return ('%.*f' % (digits, v)).replace('.', ',') + '%'


def _nice_step(x):
    """Bước chia lưới 'tròn': 1 / 2 / 5 × 10^n."""
    if not x or x <= 0:
        return 1.0
    p = 10 ** math.floor(math.log10(x))
    n = x / p
    return (1 if n <= 1 else 2 if n <= 2 else 5 if n <= 5 else 10) * p


# ----------------------------------------------------------------------
# Biểu đồ đường có tô vùng, tách màu phần âm
# ----------------------------------------------------------------------
def line_chart(vals, labels, W, H, pad_l, pad_r, pad_t, pad_b, uid,
               annotate_first_negative=False, tick_font=10,
               grid_font=10, stroke=2.25):
    """Đường số dư + vùng tô, đoạn ÂM tô đỏ đè lên.

    Cách tách màu: vẽ vùng hai lần với hai clip-path — nửa trên đường 0
    tô teal, nửa dưới tô đỏ. Làm vậy để chỗ đường cắt trục 0 đổi màu
    đúng ngay tại điểm cắt, không bị gãy khúc như khi cắt theo điểm dữ
    liệu.
    """
    if not vals:
        return Markup('')
    lo, hi = min([0.0] + list(vals)), max([0.0] + list(vals))
    step = _nice_step((hi - lo) / 4.0) or 1.0
    vmin = math.floor(lo / step) * step
    vmax = math.ceil(hi / step) * step
    span = (vmax - vmin) or 1.0
    n = len(vals)

    def X(i):
        return pad_l + (i * (W - pad_l - pad_r) / (n - 1) if n > 1 else 0)

    def Y(v):
        return pad_t + (vmax - v) * (H - pad_t - pad_b) / span

    pts = ' '.join('%.1f,%.1f' % (X(i), Y(v)) for i, v in enumerate(vals))
    area = ('M%.1f,%.1f L' % (X(0), Y(0))
            + ' L'.join('%.1f,%.1f' % (X(i), Y(v))
                        for i, v in enumerate(vals))
            + ' L%.1f,%.1f Z' % (X(n - 1), Y(0)))
    zero_y = Y(0)

    # đoạn âm: nối liên tục từ điểm trước điểm âm đầu tới điểm sau điểm
    # âm cuối, vẽ đè lên đường chính
    neg_idx = [i for i, v in enumerate(vals) if v < 0]
    neg_pts = ''
    if neg_idx:
        a = max(0, neg_idx[0] - 1)
        b = min(n - 1, neg_idx[-1] + 1)
        neg_pts = ' '.join('%.1f,%.1f' % (X(i), Y(vals[i]))
                           for i in range(a, b + 1))

    parts = []
    parts.append(
        '<svg viewBox="0 0 %d %d" width="100%%" height="%d" '
        'style="display:block;margin-top:6px">' % (W, H, H))
    parts.append(
        '<defs><clipPath id="%sTop"><rect x="0" y="0" width="%d" '
        'height="%.1f"/></clipPath><clipPath id="%sBot"><rect x="0" '
        'y="%.1f" width="%d" height="%.1f"/></clipPath></defs>'
        % (uid, W, zero_y, uid, zero_y, W, H - zero_y))

    g = vmin
    while g <= vmax + step / 100.0:
        y = Y(g)
        parts.append(
            '<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="%s" '
            'stroke-width="1"/>' % (pad_l, y, W - 8, y, C['line2']))
        parts.append(
            '<text x="%d" y="%.1f" text-anchor="end" font-size="%s" '
            'fill="%s">%s</text>'
            % (pad_l - 6, y - 3, grid_font, C['faint'], escape(fmt(g))))
        g += step

    parts.append(
        '<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="%s" '
        'stroke-width="1.25"/>'
        % (pad_l, zero_y, W - 8, zero_y, C['navy']))
    parts.append('<path d="%s" fill="%s" opacity="0.28" '
                 'clip-path="url(#%sTop)"/>' % (area, C['teal'], uid))
    parts.append('<path d="%s" fill="%s" opacity="0.38" '
                 'clip-path="url(#%sBot)"/>' % (area, C['red'], uid))
    parts.append('<polyline points="%s" fill="none" stroke="%s" '
                 'stroke-width="%s" stroke-linejoin="round"/>'
                 % (pts, C['teal'], stroke))
    if neg_pts:
        parts.append('<polyline points="%s" fill="none" stroke="%s" '
                     'stroke-width="%s" stroke-linejoin="round"/>'
                     % (neg_pts, C['red'], stroke))
    for i, v in enumerate(vals):
        parts.append('<circle cx="%.1f" cy="%.1f" r="3" fill="%s"/>'
                     % (X(i), Y(v), C['red'] if v < 0 else C['teal']))
    for i, lb in enumerate(labels):
        parts.append(
            '<text x="%.1f" y="%d" text-anchor="middle" font-size="%s" '
            'fill="%s">%s</text>'
            % (X(i), H - 8, tick_font, C['muted'], escape(lb)))

    if annotate_first_negative and neg_idx:
        i = neg_idx[0]
        bx = min(X(i) + 8, W - 236)
        parts.append(
            '<line x1="%.1f" y1="14" x2="%.1f" y2="%d" stroke="%s" '
            'stroke-width="1" stroke-dasharray="3 3"/>'
            % (X(i), X(i), H - 26, C['red']))
        parts.append(
            '<circle cx="%.1f" cy="%.1f" r="5" fill="%s" stroke="#fff" '
            'stroke-width="1.5"/>' % (X(i), Y(vals[i]), C['red']))
        parts.append(
            '<rect x="%.1f" y="6" width="228" height="22" rx="2" '
            'fill="%s"/>' % (bx, C['red']))
        parts.append(
            '<text x="%.1f" y="21" font-size="11" font-weight="600" '
            'fill="#fff">%s</text>'
            % (bx + 9, escape('Kỳ âm đầu tiên · %s · %s'
                              % (labels[i], fmt(vals[i])))))
    parts.append('</svg>')
    return Markup(''.join(parts))


# ----------------------------------------------------------------------
# Biểu đồ thác nước — chuỗi nhu cầu vốn
# ----------------------------------------------------------------------
def waterfall(steps, W=400, H=218):
    """Thác nước: cột 'total' đứng từ đáy, cột 'delta' trừ dần xuống.

    `steps`: list dict {kind: total|delta|result|risk, value, n1, n2}
    Chiều cao quy theo cột ĐẦU TIÊN (chi phí còn phải chi) chứ không
    theo cột lớn nhất — để mắt đọc được ngay "trừ đi bao nhiêu phần của
    tổng", đó mới là ý nghĩa của chuỗi này.
    """
    top, bot_axis = 22, 168
    plot = bot_axis - top
    scale = max(steps[0]['value'] if steps else 1.0, 1.0)
    bw = 46
    gap = ((W - 16 - len(steps) * bw) / (len(steps) - 1)
           if len(steps) > 1 else 0)

    def h(v):
        return max(3.0, abs(v) / scale * plot)

    parts = ['<svg viewBox="0 0 %d %d" width="100%%" height="%d" '
             'style="display:block;margin-top:4px">' % (W, H, H)]
    parts.append('<line x1="8" y1="%d" x2="%d" y2="%d" stroke="%s" '
                 'stroke-width="1"/>'
                 % (bot_axis, W - 8, bot_axis, C['line']))
    run = 0.0
    prev_x = None
    for i, s in enumerate(steps):
        x = 8 + i * (bw + gap)
        if s['kind'] == 'delta':
            hh = h(s['value'])
            run -= abs(s['value'])
            y = bot_axis - h(run) - hh
            fill = '#7FB6BE'
        else:
            run = s['value']
            hh = h(s['value'])
            y = bot_axis - hh
            fill = (C['red'] if s['kind'] == 'risk'
                    else C['teal'] if s['kind'] == 'result' else C['ink'])
        parts.append('<rect x="%.1f" y="%.1f" width="%d" height="%.1f" '
                     'fill="%s" rx="1"/>' % (x, y, bw, hh, fill))
        parts.append(
            '<text x="%.1f" y="%.1f" text-anchor="middle" font-size="10.5" '
            'font-weight="700" fill="%s">%s</text>'
            % (x + bw / 2.0, y - 6, C['navy'],
               escape(('−' if s['kind'] == 'delta' else '')
                      + fmt(abs(s['value'])))))
        parts.append(
            '<text x="%.1f" y="%d" text-anchor="middle" font-size="9.5" '
            'fill="%s">%s</text>'
            % (x + bw / 2.0, bot_axis + 15, C['muted'], escape(s['n1'])))
        if s.get('n2'):
            parts.append(
                '<text x="%.1f" y="%d" text-anchor="middle" '
                'font-size="9.5" fill="%s">%s</text>'
                % (x + bw / 2.0, bot_axis + 27, C['muted'],
                   escape(s['n2'])))
        if prev_x is not None:
            parts.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" '
                         'stroke="#A9B7BE" stroke-width="1" '
                         'stroke-dasharray="2 2"/>'
                         % (prev_x, y, x + bw, y))
        prev_x = x
    parts.append('</svg>')
    return Markup(''.join(parts))


# ----------------------------------------------------------------------
# Đồng hồ tỷ lệ sử dụng — nửa cung tròn
# ----------------------------------------------------------------------
def gauge(pct, center_text, center_sub, threshold=75.0):
    """Nửa cung tròn 0→100%, có vạch ngưỡng cảnh báo.

    Kim và màu cung đổi theo mức: <75% xanh · 75-90% vàng · ≥90% đỏ.
    """
    W, H, cx, cy, r, sw = 330, 132, 165, 108, 78, 18

    def pt(a):
        return (cx + r * math.cos(math.pi * (1 - a)),
                cy - r * math.sin(math.pi * (1 - a)))

    def arc(a0, a1, color):
        x0, y0 = pt(a0)
        x1, y1 = pt(a1)
        return ('<path d="M%.1f,%.1f A%d,%d 0 0 1 %.1f,%.1f" fill="none" '
                'stroke="%s" stroke-width="%d" stroke-linecap="butt"/>'
                % (x0, y0, r, r, x1, y1, color, sw))

    f = max(0.0, min(1.0, (pct or 0.0) / 100.0))
    color = (C['red'] if pct >= 90 else C['amber'] if pct >= threshold
             else C['green'])
    parts = ['<svg viewBox="0 0 %d %d" width="100%%" height="%d" '
             'style="display:block;margin-top:4px">' % (W, H, H)]
    parts.append(arc(0, 1, C['line2']))
    parts.append(arc(0, threshold / 100.0, '#B7DDD9'))
    if f > 0.001:
        parts.append(arc(0, f, color))
    nx, ny = pt(f)
    parts.append('<line x1="%d" y1="%d" x2="%.1f" y2="%.1f" stroke="%s" '
                 'stroke-width="2"/>' % (cx, cy, nx, ny, C['navy']))
    parts.append('<circle cx="%d" cy="%d" r="4" fill="%s"/>'
                 % (cx, cy, C['navy']))
    parts.append('<text x="%d" y="%d" text-anchor="middle" font-size="30" '
                 'font-weight="700" fill="%s">%s</text>'
                 % (cx, cy - 26, C['navy'], escape(center_text)))
    parts.append('<text x="%d" y="%d" text-anchor="middle" '
                 'font-size="10.5" fill="%s">%s</text>'
                 % (cx, cy - 9, C['muted'], escape(center_sub)))
    parts.append('<text x="%d" y="%d" text-anchor="middle" font-size="10" '
                 'fill="%s">0%%</text>' % (cx - r - 4, cy + 17, C['faint']))
    parts.append('<text x="%d" y="%d" text-anchor="middle" font-size="10" '
                 'fill="%s">100%%</text>' % (cx + r + 4, cy + 17, C['faint']))
    parts.append('<text x="%d" y="%d" text-anchor="middle" font-size="10" '
                 'fill="#9A6412">ngưỡng %d%%</text>'
                 % (cx + 62, cy - r + 4, int(threshold)))
    parts.append('</svg>')
    return Markup(''.join(parts))


# ----------------------------------------------------------------------
def donut(segs, center_top, center_sub):
    """Vành khuyên + chú giải bên phải (nhãn · số tiền · %)."""
    W, H, cx, cy, r, sw = 300, 176, 88, 84, 56, 22
    total = sum(s['value'] for s in segs) or 1.0
    circ = 2 * math.pi * r
    parts = ['<svg viewBox="0 0 %d %d" width="100%%" height="%d" '
             'style="display:block;margin-top:4px">' % (W, H, H)]
    parts.append('<circle cx="%d" cy="%d" r="%d" fill="none" '
                 'stroke="#EDF1F3" stroke-width="%d"/>' % (cx, cy, r, sw))
    off = 0.0
    for s in segs:
        ln = s['value'] / total * circ
        parts.append(
            '<circle cx="%d" cy="%d" r="%d" fill="none" stroke="%s" '
            'stroke-width="%d" stroke-dasharray="%.2f %.2f" '
            'stroke-dashoffset="%.2f" transform="rotate(-90 %d %d)"/>'
            % (cx, cy, r, s['color'], sw, ln, circ - ln, -off, cx, cy))
        off += ln
    parts.append('<text x="%d" y="%d" text-anchor="middle" font-size="17" '
                 'font-weight="700" fill="%s">%s</text>'
                 % (cx, cy - 2, C['navy'], escape(center_top)))
    parts.append('<text x="%d" y="%d" text-anchor="middle" font-size="10" '
                 'fill="%s">%s</text>'
                 % (cx, cy + 14, C['muted'], escape(center_sub)))
    for i, s in enumerate(segs):
        y = 34 + i * 30
        parts.append('<rect x="166" y="%d" width="9" height="9" rx="2" '
                     'fill="%s"/>' % (y - 9, s['color']))
        parts.append('<text x="181" y="%d" font-size="11" fill="%s">%s'
                     '</text>' % (y, C['ink'], escape(s['label'])))
        parts.append(
            '<text x="181" y="%d" font-size="12.5" font-weight="700" '
            'fill="%s">%s</text>'
            % (y + 14, C['navy'],
               escape('%s · %s' % (fmt(s['value']),
                                   pct(s['value'] / total * 100)))))
    parts.append('</svg>')
    return Markup(''.join(parts))


# ----------------------------------------------------------------------
def h_bars(rows, color=None):
    """Thanh ngang: nhãn trái · thanh · số phải."""
    W, H, l, r, top = 300, 176, 92, 62, 12
    if not rows:
        return Markup('')
    mx = max([abs(x['value']) for x in rows] + [1.0])
    bh = 17
    gap = ((H - top - 10 - len(rows) * bh) / max(1, len(rows) - 1))
    parts = ['<svg viewBox="0 0 %d %d" width="100%%" height="%d" '
             'style="display:block;margin-top:4px">' % (W, H, H)]
    for i, x in enumerate(rows):
        y = top + i * (bh + gap)
        w = max(2.0, abs(x['value']) / mx * (W - l - r))
        parts.append('<text x="%d" y="%.1f" text-anchor="end" '
                     'font-size="10.5" fill="%s">%s</text>'
                     % (l - 8, y + 12, C['ink'], escape(x['label'])))
        parts.append('<rect x="%d" y="%.1f" width="%.1f" height="%d" rx="2" '
                     'fill="%s"/>'
                     % (l, y, w, bh, x.get('color') or color or C['teal']))
        parts.append('<text x="%.1f" y="%.1f" font-size="11" '
                     'font-weight="700" fill="%s">%s</text>'
                     % (l + w + 6, y + 12, C['navy'],
                        escape(x.get('text') or fmt(x['value']))))
    parts.append('</svg>')
    return Markup(''.join(parts))


# ----------------------------------------------------------------------
def col_bars(cols):
    """Cột đứng, mỗi cột hai dòng nhãn + dòng đếm bản ghi."""
    W, H, base, top = 300, 176, 128, 26
    if not cols:
        return Markup('')
    mx = max([abs(c['value']) for c in cols] + [1.0])
    bw = 38
    gap = (W - 16 - len(cols) * bw) / max(1, len(cols) - 1)
    parts = ['<svg viewBox="0 0 %d %d" width="100%%" height="%d" '
             'style="display:block;margin-top:4px">' % (W, H, H)]
    parts.append('<line x1="8" y1="%d" x2="%d" y2="%d" stroke="%s" '
                 'stroke-width="1"/>' % (base, W - 8, base, C['line']))
    for i, c in enumerate(cols):
        hh = max(3.0, abs(c['value']) / mx * (base - top))
        x = 8 + i * (bw + gap)
        parts.append('<rect x="%.1f" y="%.1f" width="%d" height="%.1f" '
                     'rx="2" fill="%s"/>'
                     % (x, base - hh, bw, hh, c['color']))
        parts.append('<text x="%.1f" y="%.1f" text-anchor="middle" '
                     'font-size="10.5" font-weight="700" fill="%s">%s</text>'
                     % (x + bw / 2.0, base - hh - 6, C['navy'],
                        escape(fmt(c['value']))))
        parts.append('<text x="%.1f" y="%d" text-anchor="middle" '
                     'font-size="9.5" fill="%s">%s</text>'
                     % (x + bw / 2.0, base + 14, C['muted'],
                        escape(c['l1'])))
        if c.get('l2'):
            parts.append('<text x="%.1f" y="%d" text-anchor="middle" '
                         'font-size="9.5" fill="%s">%s</text>'
                         % (x + bw / 2.0, base + 26, C['muted'],
                            escape(c['l2'])))
        parts.append('<text x="%.1f" y="%d" text-anchor="middle" '
                     'font-size="9.5" fill="%s">%s KW</text>'
                     % (x + bw / 2.0, base + 42, C['faint'], c['count']))
    parts.append('</svg>')
    return Markup(''.join(parts))


# ----------------------------------------------------------------------
def timeline(items, today, W=1290):
    """Dòng thời gian hiệu lực HĐTD.

    `items`: [{code, bank, date_from, date_to|None, days|None, }]
    HĐTD chưa khai ngày hết hiệu lực vẽ XÁM + đuôi nét đứt — để trống là
    "chưa đủ dữ liệu", KHÔNG được coi như còn hiệu lực dài.
    """
    l, r, top, row_h = 232, 96, 26, 26
    H = top + max(1, len(items)) * row_h + 30
    if not items:
        return Markup('')
    starts = [it['date_from'] for it in items if it.get('date_from')]
    ends = [it['date_to'] for it in items if it.get('date_to')]
    y0 = min([d.year for d in starts] + [today.year])
    y1 = max([d.year for d in ends] + [today.year]) + 1
    t0 = date(y0, 1, 1).toordinal()
    t1 = date(y1 + 1, 1, 1).toordinal()

    def X(d):
        return l + (d.toordinal() - t0) / float(t1 - t0) * (W - l - r)

    parts = ['<svg viewBox="0 0 %d %d" width="100%%" height="%d" '
             'style="display:block;margin-top:6px">' % (W, H, H)]
    for y in range(y0, y1 + 1):
        x = X(date(y, 1, 1))
        parts.append('<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" '
                     'stroke="#EDF1F3" stroke-width="1"/>'
                     % (x, top - 12, x, top + len(items) * row_h))
        parts.append('<text x="%.1f" y="%d" text-anchor="middle" '
                     'font-size="10" fill="%s">%d</text>'
                     % (x, top - 16, C['faint'], y))
    tx = X(today)
    parts.append('<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" stroke="%s" '
                 'stroke-width="1.25" stroke-dasharray="3 3"/>'
                 % (tx, top - 12, tx, top + len(items) * row_h + 6,
                    C['navy']))
    parts.append('<text x="%.1f" y="%d" font-size="10" font-weight="600" '
                 'fill="%s">Hôm nay %s</text>'
                 % (tx + 5, top + len(items) * row_h + 18, C['navy'],
                    today.strftime('%d/%m/%Y')))
    for i, it in enumerate(items):
        y = top + i * row_h
        na = not it.get('date_to')
        color = (C['gray'] if na
                 else C['amber'] if it['days'] < 90 else C['teal'])
        xa = X(it['date_from']) if it.get('date_from') else X(today)
        xb = X(today) if na else X(it['date_to'])
        parts.append('<text x="4" y="%d" font-size="11.5" '
                     'font-weight="600" fill="%s">%s</text>'
                     % (y + 13, C['navy'], escape(it['code'])))
        parts.append('<text x="112" y="%d" font-size="11" fill="%s">%s'
                     '</text>' % (y + 13, C['muted'], escape(it['bank'])))
        parts.append('<rect x="%.1f" y="%d" width="%.1f" height="13" '
                     'rx="3" fill="%s" opacity="%s"/>'
                     % (xa, y + 3, max(3.0, xb - xa), color,
                        '0.55' if na else '1'))
        if na:
            parts.append('<rect x="%.1f" y="%d" width="26" height="13" '
                         'rx="3" fill="none" stroke="%s" stroke-width="1" '
                         'stroke-dasharray="3 2"/>' % (xb, y + 3, C['gray']))
        parts.append(
            '<text x="%d" y="%d" font-size="11" font-weight="%s" '
            'fill="%s">%s</text>'
            % (W - r + 8, y + 14, '400' if na else '700',
               C['muted'] if na else ('#9A6412' if it['days'] < 90
                                      else C['ink']),
               escape('Chưa đủ dữ liệu' if na
                      else 'còn %d ngày' % it['days'])))
    parts.append('</svg>')
    return Markup(''.join(parts))
